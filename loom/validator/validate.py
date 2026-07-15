"""Validator entry point. Returns the accumulated ValidationFailure list."""
from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError

from loom.ir.models import (
    AgentNode,
    AnyNode,
    CodeNode,
    ConditionNode,
    HTTPNode,
    IRDocument,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    RetrievalNode,
    TriggerNode,
)
from loom.ir.schema import load_schema_for_doc
from loom.validator.errors import ValidationFailure
from loom.validator.policy import check_policy
from loom.validator.refs import RefParseError, parse_refs
from loom.validator.registry import Registry, RegistryEntryNotFound
from loom.validator.typecheck import TypeExpr, TypeMismatch, parallel_merge_type, to_failure

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def validate(
    doc: dict[str, Any],
    *,
    scope: str,
    audit_max_retention_days: int = 365,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    # 1. JSON Schema (returns all errors at once).
    try:
        schema = load_schema_for_doc(doc)
    except ValueError as e:
        return [ValidationFailure("schema", str(e))]
    for err in Draft202012Validator(schema).iter_errors(doc):
        failures.append(ValidationFailure(
            "schema", err.message, location=_loc(err.absolute_path),
        ))
    if failures:
        return failures

    # 2. Pydantic (catches what JSON Schema oneOf can't always pin).
    try:
        ir = IRDocument.model_validate(doc)
    except ValidationError as e:
        for err in e.errors():
            failures.append(ValidationFailure(
                "schema", err["msg"], location=".".join(str(p) for p in err["loc"]),
            ))
        return failures

    by_id = {n.id: n for n in _walk(ir.nodes)}

    # 3. Graph structure: unique ids, cardinality, dangling edges/branches,
    #    reachability, and cycles in the top-level control-flow graph.
    graph_failures, ancestors = _check_graph(ir)
    failures.extend(graph_failures)

    # 4. Reference parse + upstream/scope resolution + field-path type-flow.
    failures.extend(_check_references(ir, ancestors, by_id))
    failures.extend(_check_parallel_merges(ir, by_id))

    # 5. Registry pin + resolution (scope-aware) + declared-usage cross-check.
    failures.extend(_check_registry(ir, scope=scope))

    # 6. Per-node policy invariants (includes mandatory security policy).
    failures.extend(check_policy(ir, audit_max_retention_days=audit_max_retention_days))

    return failures


# ---------------------------------------------------------------------------
# Graph structure: ids, cardinality, edges/branches/fallback endpoints,
# reachability, cycles.
# ---------------------------------------------------------------------------


def _check_graph(ir: IRDocument) -> tuple[list[ValidationFailure], dict[str, set[str]]]:
    failures: list[ValidationFailure] = []

    seen_ids: set[str] = set()
    trigger_ids: list[str] = []
    output_count = 0
    for n in _walk(ir.nodes):
        if n.id in seen_ids:
            failures.append(ValidationFailure(
                "reference", f"duplicate node id {n.id!r}", location=f"nodes[{n.id}]",
            ))
        seen_ids.add(n.id)
        if isinstance(n, TriggerNode):
            trigger_ids.append(n.id)
        if isinstance(n, OutputNode):
            output_count += 1
    if len(trigger_ids) != 1:
        failures.append(ValidationFailure(
            "reference", f"workflow must have exactly one trigger node, found {len(trigger_ids)}",
        ))
    if output_count < 1:
        failures.append(ValidationFailure(
            "reference", "workflow must have at least one output node",
        ))

    top_ids = {n.id for n in ir.nodes}
    data_parents: dict[str, set[str]] = {i: set() for i in top_ids}
    forward: dict[str, set[str]] = {i: set() for i in top_ids}

    def add_edge(src: str, dst: str, *, carries_data: bool, loc: str) -> None:
        if src not in top_ids:
            failures.append(ValidationFailure(
                "reference", f"edge references unknown node {src!r}", location=loc,
            ))
            return
        if dst not in top_ids:
            failures.append(ValidationFailure(
                "reference", f"edge references unknown node {dst!r}", location=loc,
            ))
            return
        forward[src].add(dst)
        if carries_data:
            data_parents[dst].add(src)

    for i, e in enumerate(ir.edges):
        add_edge(e.from_, e.to, carries_data=e.data, loc=f"edges[{i}]")
    for n in ir.nodes:
        if isinstance(n, ConditionNode):
            for bi, b in enumerate(n.branches):
                add_edge(n.id, b.next, carries_data=True, loc=f"nodes[{n.id}].branches[{bi}].next")
            if n.default is not None:
                add_edge(n.id, n.default, carries_data=True, loc=f"nodes[{n.id}].default")
        if isinstance(n, AgentNode) and n.fallback_edge is not None:
            add_edge(n.id, n.fallback_edge, carries_data=True, loc=f"nodes[{n.id}].fallback_edge")

    if len(trigger_ids) == 1:
        failures.extend(_reachability_and_cycles(top_ids, forward, trigger_ids[0]))

    ancestors = _ancestor_closure(data_parents)
    return failures, ancestors


def _reachability_and_cycles(
    top_ids: set[str], forward: dict[str, set[str]], trigger_id: str,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    reached = {trigger_id}
    stack = [trigger_id]
    while stack:
        cur = stack.pop()
        for nxt in forward.get(cur, ()):
            if nxt not in reached:
                reached.add(nxt)
                stack.append(nxt)
    for nid in sorted(top_ids - reached):
        failures.append(ValidationFailure(
            "reference", f"node {nid!r} is not reachable from the trigger", location=f"nodes[{nid}]",
        ))

    white, gray, black = 0, 1, 2
    color = dict.fromkeys(top_ids, white)
    found_cycle = False

    def dfs(u: str) -> None:
        nonlocal found_cycle
        color[u] = gray
        for v in forward.get(u, ()):
            if color.get(v) == gray:
                found_cycle = True
            elif color.get(v) == white:
                dfs(v)
        color[u] = black

    for nid in top_ids:
        if color[nid] == white:
            dfs(nid)
    if found_cycle:
        failures.append(ValidationFailure(
            "reference", "workflow graph contains a cycle outside declared loop nodes",
        ))
    return failures


def _ancestor_closure(data_parents: dict[str, set[str]]) -> dict[str, set[str]]:
    memo: dict[str, set[str]] = {}

    def visit(nid: str, stack: frozenset[str]) -> set[str]:
        if nid in memo:
            return memo[nid]
        if nid in stack:
            return set()  # cycle guard; already reported by _reachability_and_cycles
        stack = stack | {nid}
        acc: set[str] = set()
        for p in data_parents.get(nid, ()):
            acc.add(p)
            acc |= visit(p, stack)
        memo[nid] = acc
        return acc

    for nid in data_parents:
        visit(nid, frozenset())
    return memo


# ---------------------------------------------------------------------------
# Reference legality (upstream + scope) and field-path type-flow.
# ---------------------------------------------------------------------------


def _compute_ref_scopes(
    ir: IRDocument, ancestors: dict[str, set[str]],
) -> tuple[dict[str, tuple[set[str], frozenset[str]]], dict[str, tuple[set[str], frozenset[str]]]]:
    """node_id -> (legal producer ids, visible loop variables).

    Top-level nodes may only reference their ancestors in the control-flow
    graph. Nodes nested in a loop body or parallel branch may additionally
    reference any sibling in the same body/branch — bodies have no `edges`
    construct of their own, so sibling order can't establish "upstream".
    A LoopNode's own `collect` expression is evaluated after its body runs,
    so it gets a separate, wider scope (returned as `collect_scopes`).
    """
    top_ids = {n.id for n in ir.nodes}
    scopes: dict[str, tuple[set[str], frozenset[str]]] = {}
    collect_scopes: dict[str, tuple[set[str], frozenset[str]]] = {}

    def visit(nodes: list[AnyNode], enclosing_allowed: frozenset[str], loop_vars: frozenset[str]) -> None:
        local_ids = {n.id for n in nodes}
        for n in nodes:
            if n.id in top_ids:
                allowed = set(ancestors.get(n.id, set()))
            else:
                allowed = set(enclosing_allowed) | (local_ids - {n.id})
            scopes[n.id] = (allowed, loop_vars)
            if isinstance(n, LoopNode):
                inner_allowed = allowed | {n.id}
                body_ids = {b.id for b in n.body}
                collect_scopes[n.id] = (inner_allowed | body_ids, loop_vars | {n.as_})
                visit(n.body, frozenset(inner_allowed), loop_vars | {n.as_})
            elif isinstance(n, ParallelNode):
                inner_allowed = allowed | {n.id}
                for branch in n.branches.values():
                    visit(branch, frozenset(inner_allowed), loop_vars)

    visit(ir.nodes, frozenset(), frozenset())
    return scopes, collect_scopes


def _check_references(
    ir: IRDocument, ancestors: dict[str, set[str]], by_id: dict[str, AnyNode],
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    scopes, collect_scopes = _compute_ref_scopes(ir, ancestors)
    input_names = {p.name for p in ir.inputs}

    for field_label, txt, loc, node_id in _iter_string_fields(ir):
        if field_label == "collect" and node_id in collect_scopes:
            allowed, loop_vars = collect_scopes[node_id]
        else:
            allowed, loop_vars = scopes.get(node_id, (set(), frozenset()))
        try:
            refs = parse_refs(txt)
        except RefParseError as e:
            failures.append(ValidationFailure("reference", str(e), location=loc))
            continue
        for ref in refs:
            if ref.node_id == "input":
                if not ref.path or ref.path[0] not in input_names:
                    failures.append(ValidationFailure(
                        "reference",
                        f"${{input.{'.'.join(ref.path)}}} references an undeclared input",
                        location=loc,
                    ))
                continue
            if ref.node_id in loop_vars:
                continue  # per-iteration loop variable; opaque to the type layer
            if ref.node_id not in allowed:
                failures.append(ValidationFailure(
                    "reference", f"${{{ref.node_id}.…}} not produced upstream of this node", location=loc,
                ))
                continue
            producer = by_id.get(ref.node_id)
            if producer is None:
                continue
            try:
                _resolve_ref_path(_node_output_type(producer, by_id), ref.path)
            except TypeMismatch as e:
                failures.append(to_failure(e, location=loc))
    return failures


def _resolve_ref_path(root: TypeExpr, path: tuple[str, ...]) -> None:
    cur = root
    for seg in path:
        if cur.name in ("any", "json"):
            return  # opaque beyond this point
        if re.fullmatch(r"\[\d+\]", seg):
            if cur.name != "array":
                raise TypeMismatch(f"index {seg} on non-array type {cur.name}")
            cur = cur.params[0]
            continue
        if cur.name == "object":
            match = next((v for k, v in cur.fields if k == seg), None)
            if match is None:
                raise TypeMismatch(f"field {seg!r} not declared in producer output")
            cur = match
            continue
        raise TypeMismatch(f"cannot access {seg!r} on type {cur.name}")


# ---------------------------------------------------------------------------
# Declared output shape per node type (best-effort; "any" where the IR
# doesn't declare a shape, e.g. free-text LLM output or raw HTTP responses).
# ---------------------------------------------------------------------------

_JSON_PRIM = {"string": "string", "boolean": "boolean", "null": "null", "number": "number", "integer": "number"}


def _json_schema_to_type(schema: Any) -> TypeExpr:
    if not isinstance(schema, dict):
        return TypeExpr(name="any")
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties")
        if not isinstance(props, dict):
            return TypeExpr(name="any")
        return TypeExpr(name="object", fields=tuple((k, _json_schema_to_type(v)) for k, v in props.items()))
    if t == "array":
        return TypeExpr(name="array", params=(_json_schema_to_type(schema.get("items")),))
    if isinstance(t, str) and t in _JSON_PRIM:
        return TypeExpr(name=_JSON_PRIM[t])
    return TypeExpr(name="any")


def _node_output_type(node: AnyNode, by_id: dict[str, AnyNode]) -> TypeExpr:
    if isinstance(node, (LLMNode, CodeNode)):
        return _json_schema_to_type(node.output_schema) if node.output_schema else TypeExpr(name="any")
    if isinstance(node, AgentNode):
        return _json_schema_to_type(node.output_schema)
    if isinstance(node, RetrievalNode):
        return TypeExpr(name="object", fields=(("chunks", TypeExpr(name="chunks")),))
    # LoopNode/ParallelNode aggregated-output field naming has no single
    # convention across existing archetypes/templates (`${loop.item}` vs
    # `${loop.<as>}` vs bare `${<as>}`; `${parallel.<branch_key>}` vs a single
    # custom field) — stay permissive on field-path checks for these rather
    # than reject a legitimate authoring convention. Branch-type consistency
    # for parallel merges is still checked separately (_check_parallel_merges).
    return TypeExpr(name="any")


def _last(nodes: list[AnyNode]) -> AnyNode | None:
    return nodes[-1] if nodes else None


def _check_parallel_merges(ir: IRDocument, by_id: dict[str, AnyNode]) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    for n in _walk(ir.nodes):
        if not isinstance(n, ParallelNode):
            continue
        branch_keys = list(n.branches.keys())
        branch_types = [
            _node_output_type(terminal, by_id) if (terminal := _last(n.branches[k])) is not None else TypeExpr(name="any")
            for k in branch_keys
        ]
        try:
            parallel_merge_type(n.merge_strategy, branch_types, branch_keys=branch_keys)
        except TypeMismatch as e:
            failures.append(to_failure(e, location=f"nodes[{n.id}]"))
    return failures


# ---------------------------------------------------------------------------
# Registry: pin verification + scope-aware resolution + declared-usage
# cross-check.
# ---------------------------------------------------------------------------


def _check_registry(ir: IRDocument, *, scope: str) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    try:
        reg = Registry.load("v1")
    except FileNotFoundError:
        failures.append(ValidationFailure(
            "policy", "registry snapshot 'v1' not found", location="registry_ref.registry_version",
        ))
        return failures

    if reg.version != ir.registry_ref.registry_version:
        failures.append(ValidationFailure(
            "policy",
            f"registry_ref.registry_version {ir.registry_ref.registry_version!r} does not match "
            f"the resolved registry content hash {reg.version!r}",
            location="registry_ref.registry_version",
        ))

    for n in _walk(ir.nodes):
        if isinstance(n, RetrievalNode):
            try:
                reg.resolve_dataset(n.dataset, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].dataset",
                ))
            else:
                if n.dataset not in ir.registry_ref.datasets:
                    failures.append(ValidationFailure(
                        "policy",
                        f"dataset {n.dataset!r} used but not declared in registry_ref.datasets",
                        location=f"nodes[{n.id}].dataset",
                    ))
        if isinstance(n, HTTPNode) and n.credential is not None:
            try:
                entry = reg.resolve_credential(n.credential, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].credential",
                ))
            else:
                if n.credential not in ir.registry_ref.credentials:
                    failures.append(ValidationFailure(
                        "policy",
                        f"credential {n.credential!r} used but not declared in registry_ref.credentials",
                        location=f"nodes[{n.id}].credential",
                    ))
                for reason in _check_credentialed_http_url(n, entry):
                    failures.append(ValidationFailure("policy", reason, location=f"nodes[{n.id}].url"))
        if isinstance(n, AgentNode):
            for tool in n.tools:
                try:
                    reg.resolve_tool(tool, scope=scope)
                except RegistryEntryNotFound as e:
                    failures.append(ValidationFailure(
                        "policy", str(e), location=f"nodes[{n.id}].tools",
                    ))

    return failures


_URL_HOST_RE = re.compile(r"^(https?)://([^/\s{}]+)")
_LOOPBACK_HOSTNAMES = {"localhost"}


def _literal_url_host(url: str) -> tuple[str, str] | None:
    """(scheme, host) if `url`'s scheme+host is fully static; None if templated."""
    m = _URL_HOST_RE.match(url)
    if not m:
        return None
    scheme, host = m.group(1), m.group(2)
    if "${" in scheme or "${" in host:
        return None
    return scheme, host


def _host_matches(hostname: str, pattern: str) -> bool:
    pattern = pattern.lower()
    if pattern.startswith("*."):
        return hostname == pattern[2:] or hostname.endswith(pattern[1:])
    return hostname == pattern


def _host_is_network_internal(hostname: str) -> bool:
    if hostname in _LOOPBACK_HOSTNAMES:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_link_local or addr.is_private


def _check_credentialed_http_url(node: HTTPNode, credential: Any) -> list[str]:
    reasons: list[str] = []
    literal = _literal_url_host(node.url)
    if literal is None:
        reasons.append(
            "credentialed http node url must have a static https:// host; "
            "fully variable URLs can cross trust boundaries (SSRF)"
        )
        return reasons

    scheme, host = literal
    hostname = host.split(":")[0].lower()
    if credential.require_tls and scheme != "https":
        reasons.append(f"credentialed http url uses {scheme!r}; TLS (https) is required")

    allowed_hosts = credential.allowed_hosts
    explicitly_allowed = any(_host_matches(hostname, h) for h in allowed_hosts)
    if not allowed_hosts:
        reasons.append(f"credential {node.credential!r} has no allowed_hosts configured")
    elif not explicitly_allowed:
        reasons.append(f"http url host {hostname!r} is not in credential {node.credential!r} allowed_hosts")

    if _host_is_network_internal(hostname) and not explicitly_allowed:
        reasons.append(f"http url host {hostname!r} resolves to a loopback/link-local/private address")

    return reasons


# ---------------------------------------------------------------------------
# Tree walk + field enumeration
# ---------------------------------------------------------------------------


def _walk(nodes: Iterable[AnyNode]) -> Iterator[AnyNode]:
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)


def _iter_string_fields(ir: IRDocument) -> Iterator[tuple[str, str, str, str]]:
    """Yield (field_label, text, loc, owning_node_id) for every field that may contain VarRefs."""
    for n in _walk(ir.nodes):
        loc_base = f"nodes[{n.id}]"
        if isinstance(n, LLMNode):
            yield "prompt", n.prompt, f"{loc_base}.prompt", n.id
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt", n.id
        elif isinstance(n, RetrievalNode):
            yield "query", n.query, f"{loc_base}.query", n.id
        elif isinstance(n, HTTPNode):
            yield "url", n.url, f"{loc_base}.url", n.id
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key", n.id
            if isinstance(n.body, str):
                yield "body", n.body, f"{loc_base}.body", n.id
        elif isinstance(n, CodeNode):
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key", n.id
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}", n.id
        elif isinstance(n, AgentNode):
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt", n.id
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}", n.id
        elif isinstance(n, LoopNode):
            yield "over", n.over, f"{loc_base}.over", n.id
            if n.collect:
                yield "collect", n.collect, f"{loc_base}.collect", n.id
        elif isinstance(n, OutputNode):
            for k, v in n.bindings.items():
                yield f"bindings.{k}", v, f"{loc_base}.bindings.{k}", n.id


def _loc(path: Iterable[Any]) -> str:
    parts = []
    for p in path:
        parts.append(str(p))
    return ".".join(parts)
