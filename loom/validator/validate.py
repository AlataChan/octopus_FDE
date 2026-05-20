"""Validator entry point. Returns the accumulated ValidationFailure list."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError

from loom.ir.models import (
    AgentNode,
    AnyNode,
    CodeNode,
    HTTPNode,
    IRDocument,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    RetrievalNode,
)
from loom.ir.schema import load_schema_for_doc
from loom.validator.errors import ValidationFailure
from loom.validator.policy import check_policy
from loom.validator.refs import RefParseError, parse_refs
from loom.validator.registry import Registry, RegistryEntryNotFound

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def validate(doc: dict[str, Any], *, scope: str) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    # 1. JSON Schema (returns all errors at once)
    schema = load_schema_for_doc(doc)
    for err in Draft202012Validator(schema).iter_errors(doc):
        failures.append(ValidationFailure(
            "schema", err.message, location=_loc(err.absolute_path),
        ))
    if failures:
        return failures

    # 2. Pydantic (catches what JSON Schema oneOf can't always pin)
    try:
        ir = IRDocument.model_validate(doc)
    except ValidationError as e:
        for err in e.errors():
            failures.append(ValidationFailure(
                "schema", err["msg"], location=".".join(str(p) for p in err["loc"]),
            ))
        return failures

    # 3. Reference parse + resolution against the producer set.
    producers = _producer_outputs(ir)
    for _ref_field, txt, loc in _iter_string_fields(ir):
        try:
            for ref in parse_refs(txt):
                if ref.node_id != "input" and ref.node_id not in producers:
                    failures.append(ValidationFailure(
                        "reference", f"${{{ref.node_id}.…}} not produced upstream",
                        location=loc,
                    ))
        except RefParseError as e:
            failures.append(ValidationFailure(
                "reference", str(e), location=loc,
            ))

    # 4. Registry resolution (scope-aware)
    reg = Registry.load("v1")
    for n in _walk(ir.nodes):
        if isinstance(n, RetrievalNode):
            try:
                reg.resolve_dataset(n.dataset, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].dataset",
                ))
        if isinstance(n, HTTPNode) and n.credential is not None:
            try:
                reg.resolve_credential(n.credential, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].credential",
                ))
        if isinstance(n, AgentNode):
            for tool in n.tools:
                try:
                    reg.resolve_tool(tool, scope=scope)
                except RegistryEntryNotFound as e:
                    failures.append(ValidationFailure(
                        "policy", str(e), location=f"nodes[{n.id}].tools",
                    ))

    # 5. Per-node policy invariants
    failures.extend(check_policy(ir))

    # 6. Type-flow check (deferred to Task 8 wiring; placeholder here so the entry
    # point is the single seam the Planner calls. Phase 1 test_validate covers
    # ref resolution; type-flow tests in test_typecheck.py exercise the lib.)
    return failures


def _producer_outputs(ir: IRDocument) -> set[str]:
    return {n.id for n in _walk(ir.nodes)}


def _walk(nodes: Iterable[AnyNode]) -> Iterator[AnyNode]:
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)


def _iter_string_fields(ir: IRDocument) -> Iterator[tuple[str, str, str]]:
    """Yield (field_label, text, loc) for every field that may contain VarRefs."""
    for n in _walk(ir.nodes):
        loc_base = f"nodes[{n.id}]"
        if isinstance(n, LLMNode):
            yield "prompt", n.prompt, f"{loc_base}.prompt"
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt"
        elif isinstance(n, RetrievalNode):
            yield "query", n.query, f"{loc_base}.query"
        elif isinstance(n, HTTPNode):
            yield "url", n.url, f"{loc_base}.url"
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key"
            if isinstance(n.body, str):
                yield "body", n.body, f"{loc_base}.body"
        elif isinstance(n, CodeNode):
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key"
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}"
        elif isinstance(n, AgentNode):
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt"
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}"
        elif isinstance(n, LoopNode):
            yield "over", n.over, f"{loc_base}.over"
            if n.collect:
                yield "collect", n.collect, f"{loc_base}.collect"
        elif isinstance(n, OutputNode):
            for k, v in n.bindings.items():
                yield f"bindings.{k}", v, f"{loc_base}.bindings.{k}"


def _loc(path: Iterable[Any]) -> str:
    parts = []
    for p in path:
        parts.append(str(p))
    return ".".join(parts)
