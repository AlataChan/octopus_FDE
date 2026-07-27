"""Security boundary for payloads sent to the third-party Planner."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from loom.fde_session.brief import WorkflowBriefDraft
from loom.fde_session.redaction import REDACTED_TEXT, has_potential_secret

PlannerBlockCategory = Literal[
    "secret",
    "email",
    "cn_mobile",
    "cn_resident_id",
    "long_digit_run",
    "detector_error",
]

_EMAIL_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9._%+-])[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}(?![a-z0-9_-])"
)
_CN_MOBILE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CN_RESIDENT_ID_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])\d{17}[0-9Xx](?![0-9A-Za-z])"
)
_BANK_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)")
_LONG_DIGIT_RUN_PATTERN = re.compile(r"(?<!\d)\d{16,}(?!\d)")
_CN_RESIDENT_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CN_RESIDENT_ID_CHECKSUM = "10X98765432"
_PLANNER_BRIEF_FIELDS = {
    "intent",
    "target_runtime",
    "scope",
    "trigger",
    "compliance_boundary",
    "data_sources",
    "credentials",
    "approval_points",
    "inputs",
    "tools",
}
_PLANNER_INPUT_FIELDS = {"name", "type", "required"}


class PlannerPayloadBlocked(ValueError):
    """Raised when a Planner payload cannot safely cross the LLM boundary."""

    def __init__(self, *, field_path: str, category: PlannerBlockCategory) -> None:
        self.field_path = field_path
        self.category = category
        super().__init__(
            f"planner payload blocked: field={field_path}, category={category}"
        )


@dataclass(frozen=True)
class PreparedPlannerPayload:
    """Value-safe data ready to pass to the service Planner callable."""

    user_message: str
    extra_context: dict[str, object] | None = None


def prepare_outbound_planner_payload(
    *,
    intent: str,
    brief: WorkflowBriefDraft | None = None,
    extra_context: dict[str, object] | None = None,
) -> PreparedPlannerPayload:
    """Validate and assemble one outbound Planner payload."""
    _ensure_safe_intent(intent, field_path="intent")
    if extra_context is not None:
        safe_context = _sanitize_extra_context(extra_context)
        return PreparedPlannerPayload(
            user_message=(
                f"{intent}\n\n"
                "# Existing workflow context\n"
                f"{json.dumps(safe_context, ensure_ascii=False, sort_keys=True)}\n\n"
                "Apply only the declared edit and preserve every field outside "
                "allowed_change_fields."
            ),
            extra_context=safe_context,
        )
    if brief is None:
        return PreparedPlannerPayload(user_message=intent)
    brief_payload = _planner_brief_payload(
        brief,
        intent_field_path="intent",
    )
    return PreparedPlannerPayload(
        user_message="\n\n".join(
            [
                intent,
                "# Workflow brief draft",
                json.dumps(brief_payload, ensure_ascii=False, sort_keys=True),
            ]
        ).strip()
    )


def _detect_sensitive_category(text: str) -> PlannerBlockCategory | None:
    if REDACTED_TEXT in text or has_potential_secret(text):
        return "secret"
    if _EMAIL_PATTERN.search(text):
        return "email"
    if _CN_MOBILE_PATTERN.search(text):
        return "cn_mobile"
    if any(
        _valid_cn_resident_id(match.group())
        for match in _CN_RESIDENT_ID_PATTERN.finditer(text)
    ):
        return "cn_resident_id"
    if _BANK_CARD_PATTERN.search(text) or _LONG_DIGIT_RUN_PATTERN.search(text):
        return "long_digit_run"
    return None


def _ensure_safe_intent(text: str, *, field_path: str) -> None:
    try:
        category = _detect_sensitive_category(text)
    except Exception as exc:  # noqa: BLE001 - detector uncertainty must fail closed
        raise PlannerPayloadBlocked(
            field_path=field_path,
            category="detector_error",
        ) from exc
    if category is not None:
        raise PlannerPayloadBlocked(
            field_path=field_path,
            category=category,
        )


def _valid_cn_resident_id(value: str) -> bool:
    total = sum(
        int(digit) * weight
        for digit, weight in zip(value[:17], _CN_RESIDENT_ID_WEIGHTS, strict=True)
    )
    expected = _CN_RESIDENT_ID_CHECKSUM[total % 11]
    return value[-1].upper() == expected


def _planner_brief_payload(
    draft: WorkflowBriefDraft,
    *,
    intent_field_path: str,
) -> dict[str, object]:
    if draft.intent is not None:
        _ensure_safe_intent(
            draft.intent,
            field_path=intent_field_path,
        )
    payload = draft.model_dump(
        mode="json",
        include=_PLANNER_BRIEF_FIELDS,
        exclude_none=True,
    )
    payload["inputs"] = [
        item.model_dump(
            mode="json",
            include=_PLANNER_INPUT_FIELDS,
            exclude_none=True,
        )
        for item in draft.inputs
    ]
    return payload


def _sanitize_extra_context(
    context: dict[str, object],
) -> dict[str, object]:
    safe_context = dict(context)
    raw_brief = safe_context.get("workflow_brief")
    if raw_brief is not None:
        draft = (
            raw_brief
            if isinstance(raw_brief, WorkflowBriefDraft)
            else WorkflowBriefDraft.model_validate(raw_brief)
        )
        safe_context["workflow_brief"] = _planner_brief_payload(
            draft,
            intent_field_path="workflow_brief.intent",
        )
    return safe_context
