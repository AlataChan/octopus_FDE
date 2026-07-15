"""Validator-feedback self-correction loop."""
from __future__ import annotations

import json
import time
from typing import Any, cast

from loom.ir.models import IRDocument
from loom.planner.client import PlannerClient
from loom.planner.types import FailureRecord, IntentRequest, PlannerResult
from loom.validator.errors import fmt_for_planner
from loom.validator.validate import validate


def plan(req: IntentRequest, *, client: PlannerClient | None = None) -> PlannerResult:
    client = client or PlannerClient()
    failures_md = ""
    total_cost = 0.0
    t0 = time.monotonic()
    attempt = 0
    last_failures: list[FailureRecord] = []
    intent = _intent_with_extra_context(req)

    while attempt < req.max_retries + 1:
        attempt += 1
        # Pass persona_brief + target through every retry — the Planner's clarification
        # policy and target-runtime redlines are persona/target-dependent. Skipping these
        # would silently regress Persona Brief enforcement on retry attempts.
        call = client.call(
            intent=intent,
            scope=req.scope,
            persona_brief=req.persona_brief,
            target=req.target,
            prior_failures_md=failures_md,
        )
        total_cost += call.cost_usd

        try:
            doc = cast("dict[str, Any]", json.loads(_extract_json(call.ir_text)))
        except (json.JSONDecodeError, ValueError) as e:
            last_failures = [FailureRecord(bucket="schema", detail=f"non-JSON output: {e}")]
            failures_md = fmt_for_planner_records(last_failures)
            continue

        validator_failures = validate(doc, scope=req.scope)
        if not validator_failures:
            ir = IRDocument.model_validate(doc)
            return PlannerResult(
                ir=ir, attempts=attempt, ok=True, failures=[],
                cost_usd=total_cost, latency_s=time.monotonic() - t0,
            )

        last_failures = [
            FailureRecord(bucket=f.bucket, detail=f.detail, location=f.location)
            for f in validator_failures
        ]
        failures_md = fmt_for_planner(validator_failures)

    return PlannerResult(
        ir=None, attempts=attempt, ok=False, failures=last_failures,
        cost_usd=total_cost, latency_s=time.monotonic() - t0,
    )


def _intent_with_extra_context(req: IntentRequest) -> str:
    if not req.extra_context:
        return req.intent
    return (
        f"{req.intent}\n\n"
        "# Existing workflow context\n"
        f"{json.dumps(req.extra_context, ensure_ascii=False, sort_keys=True)}\n\n"
        "Apply only the declared edit and preserve every field outside allowed_change_fields."
    )


def _extract_json(text: str) -> str:
    """Strip ```json fences if the model added them despite the system prompt."""
    s = text.strip()
    if s.startswith("```"):
        first = s.find("\n")
        last = s.rfind("```")
        if first != -1 and last != -1:
            s = s[first + 1 : last].strip()
    return s


def fmt_for_planner_records(records: list[FailureRecord]) -> str:
    lines = []
    for i, f in enumerate(records, 1):
        loc = f" at `{f.location}`" if f.location else ""
        lines.append(f"{i}. [{f.bucket}]{loc}: {f.detail}")
    return "\n".join(lines)
