from loom.fde_session.brief import ComplianceBoundary, DataSourceRef, TriggerSpec, WorkflowBriefDraft
from loom.fde_session.clarify_engine import DeterministicClarifyEngine


def test_deterministic_engine_direct_ready_for_complete_draft() -> None:
    draft = WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with citations.",
        trigger=TriggerSpec(mode="manual"),
        data_sources=[DataSourceRef(handle="product_kb", kind="kb")],
        success_criteria="Answer with citations.",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=["CN"],
        ),
        target_runtime="hiagent",
        scope="ecommerce/kb",
        known_edits=["Initial build."],
    )

    result = DeterministicClarifyEngine().step(
        brief=draft,
        user_message="ready",
        round_index=0,
    )

    assert result.next_action == "ready"
    assert result.question is None


def test_deterministic_engine_asks_first_blocking_field() -> None:
    result = DeterministicClarifyEngine().step(
        brief=None,
        user_message="我要一个客服 FAQ",
        round_index=0,
    )

    assert result.next_action == "ask"
    assert result.question is not None
    assert result.question.field_path == "intent_clarification"
    assert "业务目标" in result.question.text


def test_deterministic_engine_uses_intent_clarification_to_enrich_draft() -> None:
    draft = WorkflowBriefDraft(title="客服 agent", intent="我要一个客服 agent")

    result = DeterministicClarifyEngine().step(
        brief=draft,
        user_message=(
            "面向跨境电商买家，处理订单取消、物流追踪和退款规则；"
            "需要查 product_kb 和 shopify，超过 50 美元要人工审核，"
            "成功标准是输出可校验 JSON 并避免承诺赔付。"
        ),
        round_index=1,
        pending_field_paths=["intent_clarification"],
    )

    update = result.intent_update
    assert update["intent_clarifications"]
    assert update["scope"] == "ecommerce/kb"
    assert update["data_sources"]
    assert update["approval_points"]
    assert update["success_criteria"] == "输出可校验 JSON 并避免承诺赔付。"
    assert result.next_action == "ask"


def test_short_platform_answer_does_not_satisfy_intent_clarification() -> None:
    draft = WorkflowBriefDraft(title="客服 agent", intent="我要一个客服 agent")

    result = DeterministicClarifyEngine().step(
        brief=draft,
        user_message="hiagent",
        round_index=1,
        pending_field_paths=["intent_clarification"],
    )

    assert result.intent_update == {"target_runtime": "hiagent"}
    assert result.next_action == "ask"
    assert result.question is not None
    assert result.question.field_path == "intent_clarification"


def test_deterministic_engine_merges_pending_field_answer() -> None:
    draft = WorkflowBriefDraft(title="FAQ workflow", intent="Answer ecommerce FAQ questions.")

    result = DeterministicClarifyEngine().step(
        brief=draft,
        user_message="Use Dify",
        round_index=1,
        pending_field_paths=["target_runtime"],
    )

    assert result.intent_update == {"target_runtime": "dify"}
    assert result.next_action == "ask"
