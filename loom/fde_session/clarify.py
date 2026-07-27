"""Clarification policy for WorkflowBrief drafts."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from loom.fde_session.brief import WorkflowBriefDraft

if TYPE_CHECKING:
    from loom.fde_session.brief import WorkflowBrief


class ClarifyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    question: Annotated[str, StringConstraints(min_length=1)]
    severity: Literal["block", "warn"]


def missing_fields(brief: WorkflowBrief | WorkflowBriefDraft) -> list[ClarifyQuestion]:
    questions: list[ClarifyQuestion] = []
    intent = (brief.intent or "").lower()

    if isinstance(brief, WorkflowBriefDraft):
        if _needs_intent_clarification(brief):
            questions.append(
                _block(
                    "intent_clarification",
                    (
                        "请先补充业务目标、目标用户、关键场景、不能自动处理的边界，"
                        "以及什么结果才算成功。"
                    ),
                )
            )
        if not brief.target_runtime:
            questions.append(_block("target_runtime", "你希望先把这个流程生成到哪个运行平台？如果不确定，建议先选 HiAgent。"))
        if not brief.scope:
            questions.append(_block("scope", "这个流程更像哪一类业务场景？我会据此选择可用的数据、工具和凭证范围。"))
        if brief.compliance_boundary is None:
            questions.append(
                _block(
                    "compliance_boundary",
                    "这个流程会处理哪类个人信息？这决定是否需要脱敏、人工审核和合规提示。",
                )
            )

    if brief.trigger is None:
        questions.append(_block("trigger", "这个流程应该在什么时候启动？"))

    if not brief.data_sources and (_needs_retrieval_source(intent) or _needs_channel(intent)):
        if _needs_channel(intent):
            questions.append(
                _block(
                    "data_sources",
                    "它需要连接哪些店铺、渠道或业务系统？例如 Shopify、Amazon、TikTok Shop、Shein、Temu。",
                )
            )
        else:
            questions.append(
                _block(
                    "data_sources",
                    "回答问题时应该查哪些资料或知识库？例如商品知识库、政策知识库、诊所知识库。",
                )
            )

    if not brief.credentials and _needs_credential(brief, intent):
        questions.append(
            _block(
                "credentials",
                "如果要读取或写回外部系统，需要使用哪个已配置好的接口凭证？也请说明允许访问的系统域名。",
            )
        )

    if _needs_human_review(brief) and not brief.approval_points:
        questions.append(
            _block(
                "approval_points",
                "哪些情况必须交给人工审核或升级处理？例如高风险回复、退款、诊疗建议或低置信度答案。",
            )
        )

    if not (brief.success_criteria or "").strip():
        questions.append(
            _block("success_criteria", "你会用什么标准判断这个流程生成得好？请给出可检查的结果要求。")
        )

    if not brief.known_edits:
        questions.append(
            ClarifyQuestion(
                field_path="known_edits",
                question="如果你已经知道后续会怎么改这个流程，可以先告诉我；这样生成结果会更贴近你的预期。",
                severity="warn",
            )
        )

    if len((brief.intent or "").strip()) < 30:
        questions.append(
            ClarifyQuestion(
                field_path="intent",
                question="当前描述还比较短；如果方便，请补充目标用户、场景、输入输出或不能自动处理的边界。",
                severity="warn",
            )
        )

    return questions


def _block(field_path: str, question: str) -> ClarifyQuestion:
    return ClarifyQuestion(field_path=field_path, question=question, severity="block")


def _needs_intent_clarification(brief: WorkflowBriefDraft) -> bool:
    if brief.intent_clarifications:
        return False
    if (
        brief.target_runtime
        and brief.scope
        and brief.trigger is not None
        and brief.compliance_boundary is not None
        and bool((brief.success_criteria or "").strip())
    ):
        return False
    intent = (brief.intent or "").strip()
    if len(intent) < 40:
        return True
    signals = 0
    signal_groups = (
        ("用户", "客户", "买家", "患者", "客服", "operator", "buyer", "patient", "customer"),
        ("订单", "物流", "退款", "知识库", "复诊", "随访", "api", "kb", "order", "refund"),
        ("人工", "审核", "审批", "转人工", "review", "approve", "human"),
        ("成功", "标准", "输出", "json", "citation", "source", "避免", "不能"),
    )
    lower = intent.lower()
    for group in signal_groups:
        if any(token in lower or token in intent for token in group):
            signals += 1
    return signals < 2


def _needs_retrieval_source(intent: str) -> bool:
    keywords = (
        "rag", "retrieval", "retrieve", "faq", "q&a", "qa", "question", "answer",
        "citation", "source", "followup", "follow-up", "patient", "clinic", "tcm",
        "查询", "检索", "问答", "知识库", "复诊", "随访", "患者",
    )
    return any(k in intent for k in keywords)


def _needs_channel(intent: str) -> bool:
    keywords = (
        "order exception", "order-exception", "订单异常", "marketplace", "channel",
        "shopify", "amazon", "tiktok", "shein", "temu",
    )
    return any(k in intent for k in keywords)


def _needs_credential(brief: WorkflowBrief | WorkflowBriefDraft, intent: str) -> bool:
    if any(source.kind == "api" for source in brief.data_sources):
        return True
    keywords = (
        "api", "http", "writeback", "write back", "写回", "shopify", "amazon",
        "tiktok", "shein", "temu",
    )
    return any(k in intent for k in keywords)


def _needs_human_review(brief: WorkflowBrief | WorkflowBriefDraft) -> bool:
    boundary = brief.compliance_boundary
    if boundary is None:
        return False
    return boundary.pii_class_default == "high" or bool(boundary.regulatory_tags)
