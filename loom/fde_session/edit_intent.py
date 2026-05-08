"""Typed natural-language edit intents for FDE sessions."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChangeTriggerMode(_Strict):
    kind: Literal["change_trigger_mode"] = "change_trigger_mode"
    to: Literal["manual", "schedule", "webhook"]


class ChangeRetrievalTopK(_Strict):
    kind: Literal["change_retrieval_top_k"] = "change_retrieval_top_k"
    node_id: str
    to_k: Annotated[int, Field(ge=1, le=100)]


class AddRetryPolicy(_Strict):
    kind: Literal["add_retry_policy"] = "add_retry_policy"
    node_id: str
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    retry_on: list[Literal["5xx", "4xx", "timeout", "network", "rate_limit"]] = Field(
        default_factory=list
    )


class AddManualReviewGate(_Strict):
    kind: Literal["add_manual_review_gate"] = "add_manual_review_gate"
    after_node_id: str
    reviewer_role: str


class ChangeTemperature(_Strict):
    kind: Literal["change_temperature"] = "change_temperature"
    node_id: str
    to: Annotated[float, Field(ge=0, le=2)]


class AddComplianceDisclaimer(_Strict):
    kind: Literal["add_compliance_disclaimer"] = "add_compliance_disclaimer"
    node_id: str
    text: str


class MarkUnrecognized(_Strict):
    kind: Literal["mark_unrecognized"] = "mark_unrecognized"
    raw_text: str


EditIntent = Annotated[
    ChangeTriggerMode
    | ChangeRetrievalTopK
    | AddRetryPolicy
    | AddManualReviewGate
    | ChangeTemperature
    | AddComplianceDisclaimer
    | MarkUnrecognized,
    Field(discriminator="kind"),
]


def parse_edit_intent(text: str) -> EditIntent:
    raw = text.strip()
    lower = raw.lower()

    mode = _parse_trigger_mode(lower)
    if mode is not None:
        return ChangeTriggerMode(to=mode)

    disclaimer = re.search(
        r"(?:add\s+)?(?:compliance\s+)?disclaimer\s+to\s+(?P<node>[a-zA-Z_][\w]*)\s*:\s*(?P<text>.+)",
        raw,
        re.I,
    )
    if disclaimer:
        return AddComplianceDisclaimer(
            node_id=disclaimer.group("node"),
            text=disclaimer.group("text").strip(),
        )

    top_k = re.search(
        r"(?P<node>[a-zA-Z_][\w]*)\s+top[_ -]?k\s+(?:to\s+)?(?P<k>\d+)",
        lower,
    )
    if top_k:
        return ChangeRetrievalTopK(
            node_id=top_k.group("node"),
            to_k=int(top_k.group("k")),
        )

    retry = re.search(
        r"retry.*?(?:to|node)\s+(?P<node>[a-zA-Z_][\w]*).*?(?:max[_ ]?attempts|attempts)\s+(?P<attempts>\d+)",
        lower,
    )
    if retry:
        return AddRetryPolicy(
            node_id=retry.group("node"),
            max_attempts=int(retry.group("attempts")),
            retry_on=_parse_retry_on(lower),
        )

    review = re.search(
        r"(?:manual|human)\s+review.*?after\s+(?P<node>[a-zA-Z_][\w]*)(?:.*?reviewer\s+(?P<role>[a-zA-Z_][\w]*))?",
        lower,
    )
    if review:
        return AddManualReviewGate(
            after_node_id=review.group("node"),
            reviewer_role=review.group("role") or "reviewer",
        )

    temperature = re.search(
        r"(?P<node>[a-zA-Z_][\w]*)\s+temperature\s+(?:to\s+)?(?P<value>[0-9]+(?:\.[0-9]+)?)",
        lower,
    )
    if temperature:
        return ChangeTemperature(
            node_id=temperature.group("node"),
            to=float(temperature.group("value")),
        )

    return MarkUnrecognized(raw_text=raw)


def _parse_trigger_mode(text: str) -> Literal["manual", "schedule", "webhook"] | None:
    if "trigger" not in text and "触发" not in text:
        return None
    if "webhook" in text:
        return "webhook"
    if "schedule" in text or "cron" in text or "定时" in text:
        return "schedule"
    if "manual" in text or "手动" in text:
        return "manual"
    return None


def _parse_retry_on(text: str) -> list[Literal["5xx", "4xx", "timeout", "network", "rate_limit"]]:
    values: list[Literal["5xx", "4xx", "timeout", "network", "rate_limit"]] = []
    for item in ("5xx", "4xx", "timeout", "network", "rate_limit"):
        if item in text:
            values.append(item)
    if "rate limit" in text and "rate_limit" not in values:
        values.append("rate_limit")
    return values
