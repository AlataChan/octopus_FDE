"""Per-node policy invariants beyond what the JSON Schema enforces."""
from __future__ import annotations

from typing import TYPE_CHECKING

from loom.ir.models import (
    AgentNode,
    CodeNode,
    HTTPNode,
    LoopNode,
    ParallelNode,
)
from loom.validator.errors import ValidationFailure

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from loom.ir.models import AnyNode, IRDocument


def check_policy(ir: IRDocument) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    node_ids = {n.id for n in _walk(ir.nodes)}

    default_timeout = ir.policy.default_timeout_s
    default_retry_max = (
        ir.policy.default_retry.max_attempts if ir.policy.default_retry else None
    )
    default_budget = ir.policy.agent_budget

    for n in _walk(ir.nodes):
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

    return failures


def _walk(nodes: Iterable[AnyNode]) -> Iterator[AnyNode]:
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)
