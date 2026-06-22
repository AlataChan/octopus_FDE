"""Deterministic clarification engine for Self-Design sessions."""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from loom.fde_session.brief import (
    ApprovalPoint,
    ComplianceBoundary,
    CredentialBindingRef,
    DataSourceRef,
    TriggerSpec,
    WorkflowBriefDraft,
)
from loom.fde_session.clarify import ClarifyQuestion as PolicyQuestion
from loom.fde_session.clarify import missing_fields
from loom.fde_session.redaction import redact_text

QUESTIONNAIRE_AFTER_ROUNDS = 3


class ClarifyOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    value: str
    description: str | None = None


class ClarifyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    field_path: str
    options: list[ClarifyOption] | None = None
    allow_freeform: bool = True
    severity: Literal["block", "warn"] = "block"


class ClarifyEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_update: dict[str, Any] = Field(default_factory=dict)
    next_action: Literal["ask", "ready"]
    question: ClarifyQuestion | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class ClarifyEngine(Protocol):
    def step(
        self,
        *,
        brief: WorkflowBriefDraft | None,
        user_message: str,
        round_index: int,
        pending_field_paths: Sequence[str] | None = None,
    ) -> ClarifyEngineResult: ...


class DeterministicClarifyEngine:
    """Small rule-based v1 engine driven by `missing_fields()`."""

    def step(
        self,
        *,
        brief: WorkflowBriefDraft | None,
        user_message: str,
        round_index: int,
        pending_field_paths: Sequence[str] | None = None,
    ) -> ClarifyEngineResult:
        del round_index
        safe_message = redact_text(user_message)
        update: dict[str, Any] = {}
        if brief is None:
            update.update({
                "title": _title_from_message(safe_message),
                "intent": safe_message.strip(),
            })
        draft = brief or WorkflowBriefDraft(**update)
        for field_path in pending_field_paths or ():
            update.update(parse_field_answer(field_path, safe_message))
        merged = draft.model_copy(update=update)
        block = _first_blocking_question(merged)
        if block is None:
            return ClarifyEngineResult(intent_update=update, next_action="ready")
        return ClarifyEngineResult(
            intent_update=update,
            next_action="ask",
            question=question_for_policy(block),
        )


class FakeClarifyEngine:
    """Scripted engine for route and service tests."""

    def __init__(self, script: Sequence[ClarifyEngineResult]):
        self._script = list(script)
        self.calls: list[dict[str, object]] = []

    def step(
        self,
        *,
        brief: WorkflowBriefDraft | None,
        user_message: str,
        round_index: int,
        pending_field_paths: Sequence[str] | None = None,
    ) -> ClarifyEngineResult:
        self.calls.append({
            "brief": brief,
            "user_message": user_message,
            "round_index": round_index,
            "pending_field_paths": list(pending_field_paths or ()),
        })
        if not self._script:
            return DeterministicClarifyEngine().step(
                brief=brief,
                user_message=user_message,
                round_index=round_index,
                pending_field_paths=pending_field_paths,
            )
        return self._script.pop(0)


def next_blocking_questions(brief: WorkflowBriefDraft) -> list[ClarifyQuestion]:
    return [question_for_policy(q) for q in missing_fields(brief) if q.severity == "block"]


def question_for_policy(question: PolicyQuestion) -> ClarifyQuestion:
    options = _options_for_field(question.field_path)
    return ClarifyQuestion(
        text=question.question,
        field_path=question.field_path,
        options=options,
        allow_freeform=_allow_freeform(question.field_path),
        severity=question.severity,
    )


def parse_field_answer(field_path: str, answer: str) -> dict[str, Any]:
    text = answer.strip()
    lower = text.lower()
    if not text:
        return {}
    if field_path == "intent_clarification":
        update: dict[str, Any] = {}
        if _is_substantive_intent_clarification(text):
            update.update({
                "intent": redact_text(text),
                "intent_clarifications": [redact_text(text)],
                "known_edits": ["Intent clarified through FDE questioning."],
            })
        for inferred_field in (
            "target_runtime",
            "scope",
            "trigger",
            "data_sources",
            "compliance_boundary",
            "approval_points",
            "success_criteria",
        ):
            if inferred_field == "success_criteria" and not _has_success_criteria_marker(text):
                continue
            for key, value in parse_field_answer(inferred_field, text).items():
                if value not in (None, "", []):
                    update[key] = value
        return update
    if field_path == "target_runtime":
        if "dify" in lower:
            return {"target_runtime": "dify"}
        if "hiagent" in lower or "hi agent" in lower:
            return {"target_runtime": "hiagent"}
        return {}
    if field_path == "scope":
        if "clinic/ops" in lower:
            return {"scope": "clinic/ops"}
        if "clinic" in lower or "tcm" in lower or "中医" in text:
            return {"scope": "clinic/kb"}
        if "ecommerce/ops" in lower:
            return {"scope": "ecommerce/ops"}
        if "ecommerce" in lower or "电商" in text or "客服" in text:
            return {"scope": "ecommerce/kb"}
        return {}
    if field_path == "compliance_boundary":
        explicit_value = _explicit_field_value(field_path, text)
        if explicit_value in {"none", "low", "medium", "high"}:
            regulatory_tags = ["clinical"] if explicit_value == "high" else []
            return {
                "compliance_boundary": ComplianceBoundary(
                    pii_class_default=explicit_value,
                    regulatory_tags=regulatory_tags,
                    geographies=["CN"],
                )
            }
        if (
            any(token in lower for token in ("high", "clinical", "medical", "patient"))
            or any(token in text for token in ("患者", "病历", "诊断", "证件", "身份证", "处方", "高敏"))
        ):
            return {
                "compliance_boundary": ComplianceBoundary(
                    pii_class_default="high",
                    regulatory_tags=["clinical"],
                    geographies=["CN"],
                )
            }
        if "none" in lower or any(token in text for token in ("无", "不涉及", "公开资料", "匿名")):
            return {
                "compliance_boundary": ComplianceBoundary(
                    pii_class_default="none",
                    regulatory_tags=[],
                    geographies=["CN"],
                )
            }
        if (
            "medium" in lower
            or "pii" in lower
            or any(token in text for token in ("订单", "手机号", "手机", "邮箱", "地址", "联系方式", "个人信息"))
        ):
            return {
                "compliance_boundary": ComplianceBoundary(
                    pii_class_default="medium",
                    regulatory_tags=[],
                    geographies=["CN"],
                )
            }
        if (
            "low pii" in lower
            or "low personal" in lower
            or any(token in text for token in ("低敏", "一般个人信息", "昵称", "普通咨询"))
        ):
            return {
                "compliance_boundary": ComplianceBoundary(
                    pii_class_default="low",
                    regulatory_tags=[],
                    geographies=["CN"],
                )
            }
        return {}
    if field_path == "trigger":
        if "schedule" in lower or "cron" in lower or "定时" in text:
            return {"trigger": TriggerSpec(mode="schedule", schedule_cron=_cron_from_answer(text))}
        if "webhook" in lower or "callback" in lower or "回调" in text:
            return {"trigger": TriggerSpec(mode="webhook", webhook_path="/webhook/self-design")}
        if (
            "manual" in lower
            or "手动" in text
            or "chat" in lower
            or "用户问" in text
            or "客户问" in text
            or "买家" in text
        ):
            return {"trigger": TriggerSpec(mode="manual")}
        return {}
    if field_path == "data_sources":
        sources = _data_sources_from_answer(text)
        return {"data_sources": sources} if sources else {}
    if field_path == "credentials":
        credential = _credential_from_answer(text)
        return {"credentials": [credential]} if credential else {}
    if field_path == "approval_points":
        if any(token in lower for token in ("review", "approve", "human", "manager", "clinician")) or "审核" in text:
            return {
                "approval_points": [
                    ApprovalPoint(stage="before_final_action", reviewer_role=_reviewer_role(text), blocking=True)
                ]
            }
        return {}
    if field_path == "success_criteria":
        criteria = _success_criteria_from_answer(text)
        return {"success_criteria": redact_text(criteria)} if len(criteria) >= 4 else {}
    return {}


def _first_blocking_question(brief: WorkflowBriefDraft) -> PolicyQuestion | None:
    for question in missing_fields(brief):
        if question.severity == "block":
            return question
    return None


def _title_from_message(message: str) -> str:
    stripped = message.strip()
    return stripped[:80] if stripped else "Self-Design workflow"


def _explicit_field_value(field_path: str, answer: str) -> str | None:
    match = re.search(rf"(?:^|[;\n])\s*{re.escape(field_path)}\s*=\s*([^;\n]+)", answer, re.I)
    return match.group(1).strip().lower() if match else None


def _options_for_field(field_path: str) -> list[ClarifyOption] | None:
    options: dict[str, list[tuple[str, str, str]]] = {
        "target_runtime": [
            ("HiAgent", "hiagent", "优先交付到当前主平台，适合后续生成 HiAgent 应用或 ChatFlow。"),
            ("Dify", "dify", "生成 Dify YAML，适合用来验证导入和跨平台表达。"),
        ],
        "scope": [
            ("电商知识库问答", "ecommerce/kb", "围绕商品、政策、FAQ 和引用来源回答用户问题。"),
            ("电商运营流程", "ecommerce/ops", "处理订单、物流、退款、售后升级等运营动作。"),
            ("中医知识库问答", "clinic/kb", "围绕诊所知识、服务说明和咨询前信息收集。"),
            ("中医门诊运营", "clinic/ops", "处理预约、随访、复诊、库存和人工审核流程。"),
        ],
        "compliance_boundary": [
            ("不涉及个人信息", "none", "只处理公开内容、商品资料、政策说明或匿名问题。"),
            ("只涉及低敏信息", "low", "例如昵称、渠道、普通咨询内容，不包含订单和联系方式。"),
            ("涉及订单或联系方式", "medium", "例如订单号、手机号、邮箱、地址等，需要隐私保护。"),
            ("涉及病历、诊断或证件等高敏信息", "high", "必须启用更严格的脱敏、人工审核和合规提示。"),
        ],
        "trigger": [
            ("用户提问时启动", "manual", "客服、运营或用户在聊天窗口里发起请求。"),
            ("按固定时间自动运行", "schedule", "例如每天、每小时或每周生成报告和提醒。"),
            ("收到系统通知时启动", "webhook", "例如订单状态变化、退款事件或外部系统回调。"),
        ],
    }
    values = options.get(field_path)
    if values is None:
        return None
    return [ClarifyOption(label=label, value=value, description=description) for label, value, description in values]


def _allow_freeform(field_path: str) -> bool:
    return field_path not in {"target_runtime", "scope", "trigger"}


def _cron_from_answer(answer: str) -> str:
    hourly = re.search(r"(\d+)\s*h", answer.lower())
    if hourly:
        return f"0 */{hourly.group(1)} * * *"
    return "0 * * * *"


def _data_sources_from_answer(answer: str) -> list[DataSourceRef]:
    lower = answer.lower()
    sources: list[DataSourceRef] = []
    known: dict[str, tuple[str, Literal["dataset", "kb", "table", "api"]]] = {
        "product_kb": ("product_kb", "kb"),
        "policy_kb": ("policy_kb", "kb"),
        "logistics": ("logistics_api", "api"),
        "物流": ("logistics_api", "api"),
        "order": ("order_api", "api"),
        "订单": ("order_api", "api"),
        "clinic_kb": ("clinic_kb", "kb"),
        "patient_history": ("patient_history", "dataset"),
        "shopify": ("shopify_api", "api"),
        "amazon": ("amazon_mws", "api"),
    }
    for token, (handle, kind) in known.items():
        if token in lower or token.replace("_", " ") in lower:
            sources.append(DataSourceRef(handle=handle, kind=kind))
    if "知识库" in answer and not sources:
        sources.append(DataSourceRef(handle="product_kb", kind="kb"))
    if "shopify" in lower and not any(source.handle == "shopify_api" for source in sources):
        sources.append(DataSourceRef(handle="shopify_api", kind="api"))
    return sources


def _credential_from_answer(answer: str) -> CredentialBindingRef | None:
    lower = answer.lower()
    if "none" in lower or "无" in answer:
        return None
    handle_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*(?:_api|_credential|_token|_oauth)?)", answer)
    if handle_match is None:
        return None
    handle = handle_match.group(1)
    scheme: Literal["bearer", "oauth2", "api_key", "none"] = "api_key"
    if "oauth" in lower:
        scheme = "oauth2"
    elif "bearer" in lower:
        scheme = "bearer"
    return CredentialBindingRef(handle=handle, scheme=scheme)


def _reviewer_role(answer: str) -> str:
    match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*(?:_manager|_lead|_reviewer|_clinician)?)", answer)
    return match.group(1) if match else "human_reviewer"


def _success_criteria_from_answer(answer: str) -> str:
    patterns = (
        r"成功标准(?:是|为|：|:)?\s*(.+)",
        r"success criteria(?: is| are|:)?\s*(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, answer, re.I)
        if match:
            return match.group(1).strip()
    return answer.strip()


def _has_success_criteria_marker(answer: str) -> bool:
    return bool(re.search(r"成功标准|success criteria", answer, re.I))


def _is_substantive_intent_clarification(answer: str) -> bool:
    if len(answer.strip()) >= 30:
        return True
    signals = (
        "用户", "客户", "买家", "患者", "订单", "物流", "退款", "知识库",
        "人工", "审核", "审批", "成功标准", "不能", "避免",
        "customer", "buyer", "patient", "order", "refund", "review",
    )
    lower = answer.lower()
    return sum(1 for token in signals if token in lower or token in answer) >= 2
