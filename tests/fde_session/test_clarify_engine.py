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
    assert result.question.field_path == "target_runtime"


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
