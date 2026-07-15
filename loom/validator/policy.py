"""Per-node policy invariants beyond what the JSON Schema enforces."""
from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Any

from loom.ir.models import (
    AgentNode,
    CodeNode,
    HTTPNode,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    RetrievalNode,
)
from loom.validator.errors import ValidationFailure
from loom.validator.refs import RefParseError, VarRef, parse_refs

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from loom.ir.models import AnyNode, IRDocument


def check_policy(ir: IRDocument, *, audit_max_retention_days: int = 365) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    nodes = list(_walk(ir.nodes))
    node_ids = {n.id for n in nodes}
    node_by_id = {n.id: n for n in nodes}

    default_timeout = ir.policy.default_timeout_s
    default_retry_max = (
        ir.policy.default_retry.max_attempts if ir.policy.default_retry else None
    )
    default_budget = ir.policy.agent_budget

    for n in nodes:
        loc = f"nodes[{n.id}]"
        # Timeout tightening only.
        node_to = getattr(n, "timeout_s", None)
        if default_timeout is not None and node_to is not None and node_to > default_timeout:
            failures.append(ValidationFailure(
                "policy",
                f"node timeout_s {node_to} exceeds workflow default_timeout_s {default_timeout}",
                location=loc,
            ))
        # Retry tightening only.
        node_retry = getattr(n, "retry", None)
        if (
            default_retry_max is not None
            and node_retry is not None
            and node_retry.max_attempts > default_retry_max
        ):
            failures.append(ValidationFailure(
                "policy",
                f"node retry.max_attempts {node_retry.max_attempts} exceeds default {default_retry_max}",
                location=loc,
            ))
        # http POST/PUT/PATCH/DELETE: idempotency_key required (schema also enforces; we re-check).
        if isinstance(n, HTTPNode) and n.method in {"POST", "PUT", "PATCH", "DELETE"} and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", f"{n.method} without idempotency_key", location=loc,
            ))
        # code: best-practice idempotency_key when retry is enabled.
        if isinstance(n, CodeNode) and node_retry is not None and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", "code with retry must declare idempotency_key", location=loc,
            ))
        # code: sandbox allowlist — reject anything the Validator can't vet statically.
        if isinstance(n, CodeNode):
            for reason in _check_code_sandbox(n):
                failures.append(ValidationFailure("policy", reason, location=loc))
        # agent: budget tightening, fallback edge existence, tools subset.
        if isinstance(n, AgentNode):
            if default_budget is not None:
                if n.budget.max_iterations > default_budget.max_iterations:
                    failures.append(ValidationFailure(
                        "policy", "agent max_iterations exceeds workflow default", location=loc,
                    ))
                if n.budget.max_tokens > default_budget.max_tokens:
                    failures.append(ValidationFailure(
                        "policy", "agent max_tokens exceeds workflow default", location=loc,
                    ))
                if n.budget.max_wall_clock_s > default_budget.max_wall_clock_s:
                    failures.append(ValidationFailure(
                        "policy", "agent max_wall_clock_s exceeds workflow default", location=loc,
                    ))
            if n.on_budget_exhausted == "fallback" and (
                not n.fallback_edge or n.fallback_edge not in node_ids
            ):
                failures.append(ValidationFailure(
                    "policy", f"fallback_edge {n.fallback_edge!r} does not point at an existing node",
                    location=loc,
                ))
            for tool in n.tools:
                if tool not in ir.registry_ref.tools:
                    failures.append(ValidationFailure(
                        "policy", f"agent tool {tool!r} not in registry_ref.tools", location=loc,
                    ))

    if ir.ir_version == "0.4":
        failures.extend(_check_v04_policy(ir, node_by_id, audit_max_retention_days))

    failures.extend(_check_trust_boundaries(ir))

    return failures


# ---------------------------------------------------------------------------
# Code sandbox: AST/import allowlist. Anything the Validator can't vet
# statically (an import outside the allowlist, a dangerous builtin) is
# rejected — "if it can't be sandboxed, reject the code node."
# ---------------------------------------------------------------------------

_PY_IMPORT_ALLOWLIST = {
    "json", "re", "math", "statistics", "decimal", "datetime", "itertools",
    "functools", "collections", "typing", "dataclasses", "string", "textwrap",
    "uuid", "enum",
}
_PY_DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__", "open", "input"}
_PY_DANGEROUS_ATTR_ROOTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib",
    "ctypes", "multiprocessing", "threading", "requests", "urllib", "http",
    "ftplib", "smtplib", "pickle", "marshal", "ssl",
}
# Object-introspection attribute names used by classic sandbox-escape chains
# (e.g. `().__class__.__bases__[0].__subclasses__()` reaches arbitrary
# builtins without importing anything or naming a blocked root). None of the
# import-allowlisted stdlib modules need these on a workflow code node, so
# any use is rejected regardless of what object the attribute is accessed on.
_PY_DANGEROUS_ATTR_NAMES = {
    "__class__", "__bases__", "__base__", "__subclasses__", "__mro__",
    "__globals__", "__builtins__", "__import__", "__loader__", "__spec__",
    "__code__", "__closure__", "__func__", "__self__", "__dict__",
    "__getattribute__", "__reduce__", "__reduce_ex__", "__init_subclass__",
}
_JS_DANGEROUS_PATTERNS = [
    re.compile(r"\beval\("),
    re.compile(r"\bnew\s+Function\("),
    re.compile(r"\brequire\(\s*['\"](?:child_process|fs|net|dgram|http|https|os|cluster)['\"]\s*\)"),
    re.compile(r"\bfetch\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\("),
]


def _check_code_sandbox(node: CodeNode) -> list[str]:
    if node.language == "python":
        return _check_python_sandbox(node.source)
    return _check_js_sandbox(node.source)


def _check_python_sandbox(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"code does not parse as python: {e}"]

    reasons: list[str] = []
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                root = alias.name.split(".")[0]
                if root not in _PY_IMPORT_ALLOWLIST:
                    reasons.append(f"import {alias.name!r} is not in the sandbox allowlist")
        elif isinstance(stmt, ast.ImportFrom):
            root = (stmt.module or "").split(".")[0]
            if stmt.level or root not in _PY_IMPORT_ALLOWLIST:
                reasons.append(f"import from {stmt.module!r} is not in the sandbox allowlist")
        elif isinstance(stmt, ast.Name) and stmt.id in _PY_DANGEROUS_CALLS:
            reasons.append(f"reference to {stmt.id!r} is forbidden in a sandboxed code node")
        elif isinstance(stmt, ast.Attribute):
            if stmt.attr in _PY_DANGEROUS_ATTR_NAMES:
                reasons.append(
                    f"access to {stmt.attr!r} is forbidden in a sandboxed code node "
                    "(object-introspection attributes can escape the import allowlist)"
                )
            root = stmt
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in _PY_DANGEROUS_ATTR_ROOTS:
                reasons.append(f"access to {root.id!r} is forbidden in a sandboxed code node")
    return reasons


def _check_js_sandbox(source: str) -> list[str]:
    return [
        f"js source matches forbidden pattern {p.pattern!r}"
        for p in _JS_DANGEROUS_PATTERNS if p.search(source)
    ]


# ---------------------------------------------------------------------------
# Trust-boundary delimiters: prompts must not splice untrusted content
# (raw user input, retrieved KB text, external HTTP responses) directly
# into instructions without an explicit <untrusted>...</untrusted> wrapper.
# ---------------------------------------------------------------------------

_UNTRUSTED_BLOCK_RE = re.compile(r"<untrusted>.*?</untrusted>", re.S)


def _untrusted_producer_ids(ir: IRDocument) -> set[str]:
    ids = {"input"}
    for n in _walk(ir.nodes):
        if isinstance(n, (RetrievalNode, HTTPNode)):
            ids.add(n.id)
    return ids


def _check_trust_boundaries(ir: IRDocument) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    untrusted = _untrusted_producer_ids(ir)

    for n in _walk(ir.nodes):
        fields: list[tuple[str, str]] = []
        if isinstance(n, LLMNode):
            fields.append(("prompt", n.prompt))
            if n.system_prompt:
                fields.append(("system_prompt", n.system_prompt))
        elif isinstance(n, AgentNode) and n.system_prompt:
            fields.append(("system_prompt", n.system_prompt))

        for field_label, text in fields:
            spans = [(m.start(), m.end()) for m in _UNTRUSTED_BLOCK_RE.finditer(text)]
            for pid in untrusted:
                ref_re = re.compile(rf"\$\{{{re.escape(pid)}(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*\}}")
                for m in ref_re.finditer(text):
                    if not any(s <= m.start() and m.end() <= e for s, e in spans):
                        failures.append(ValidationFailure(
                            "policy",
                            f"prompt references untrusted producer {pid!r} outside a <untrusted> delimiter",
                            location=f"nodes[{n.id}].{field_label}",
                        ))
    return failures


def _check_v04_policy(
    ir: IRDocument,
    node_by_id: dict[str, AnyNode],
    audit_max_retention_days: int,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    guardrails = ir.policy.guardrails
    if guardrails is not None:
        for idx, pattern in enumerate(guardrails.custom_patterns):
            try:
                re.compile(pattern)
            except re.error as e:
                failures.append(ValidationFailure(
                    "policy",
                    f"guardrails.custom_patterns[{idx}] is not a valid regex: {e}",
                    location=f"policy.guardrails.custom_patterns[{idx}]",
                ))

    escalation = ir.policy.escalation
    if escalation is not None:
        handoff = node_by_id.get(escalation.handoff_node)
        if not isinstance(handoff, OutputNode):
            failures.append(ValidationFailure(
                "policy",
                f"escalation.handoff_node {escalation.handoff_node!r} must reference an output node",
                location="policy.escalation.handoff_node",
            ))
        failures.extend(_check_confidence_ref(escalation.confidence_from, node_by_id))

    audit = ir.policy.audit
    if audit is not None and audit.retention_days > audit_max_retention_days:
        failures.append(ValidationFailure(
            "policy",
            f"audit.retention_days {audit.retention_days} exceeds org cap {audit_max_retention_days}",
            location="policy.audit.retention_days",
        ))

    return failures


def _check_confidence_ref(
    confidence_from: str,
    node_by_id: dict[str, AnyNode],
) -> list[ValidationFailure]:
    try:
        refs = parse_refs(confidence_from)
    except RefParseError as e:
        return [ValidationFailure("policy", str(e), location="policy.escalation.confidence_from")]

    if len(refs) != 1 or confidence_from.strip() != _format_ref(refs[0]):
        return [ValidationFailure(
            "policy",
            "escalation.confidence_from must be a single VarRef",
            location="policy.escalation.confidence_from",
        )]

    ref = refs[0]
    producer = node_by_id.get(ref.node_id)
    if not isinstance(producer, LLMNode):
        return [ValidationFailure(
            "policy",
            f"escalation.confidence_from must reference an llm node output, got {ref.node_id!r}",
            location="policy.escalation.confidence_from",
        )]
    if not ref.path or ref.path[0].startswith("["):
        return [ValidationFailure(
            "policy",
            "escalation.confidence_from must reference an llm output_schema field",
            location="policy.escalation.confidence_from",
        )]

    field = ref.path[0]
    field_type = _json_schema_field_type(producer.output_schema, field)
    if field_type not in {"number", "integer"}:
        return [ValidationFailure(
            "policy",
            f"escalation.confidence_from field {field!r} must be numeric in llm.output_schema",
            location="policy.escalation.confidence_from",
        )]
    return []


def _format_ref(ref: VarRef) -> str:
    path = "".join(segment if segment.startswith("[") else f".{segment}" for segment in ref.path)
    return f"${{{ref.node_id}{path}}}"


def _json_schema_field_type(output_schema: dict[str, Any] | None, field: str) -> str | None:
    if not isinstance(output_schema, dict):
        return None
    props = output_schema.get("properties")
    if not isinstance(props, dict):
        return None
    field_schema = props.get(field)
    if not isinstance(field_schema, dict):
        return None
    raw_type = field_schema.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        for candidate in ("number", "integer"):
            if candidate in raw_type:
                return candidate
    return None


def _walk(nodes: Iterable[AnyNode]) -> Iterator[AnyNode]:
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)
