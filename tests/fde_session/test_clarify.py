from loom.fde_session.brief import ComplianceBoundary, DataSourceRef, TriggerSpec, WorkflowBrief, WorkflowBriefDraft
from loom.fde_session.clarify import missing_fields


def _brief(**overrides: object) -> WorkflowBrief:
    data = {
        "title": "Brief",
        "intent": "Build a workflow that has enough detail for safe planning.",
        "trigger": TriggerSpec(mode="manual"),
        "inputs": [],
        "data_sources": [],
        "tools": [],
        "credentials": [],
        "approval_points": [],
        "success_criteria": "Workflow produces a reviewed output.",
        "compliance_boundary": ComplianceBoundary(
            pii_class_default="medium",
            regulatory_tags=[],
            geographies=["CN"],
        ),
        "known_edits": ["Initial build."],
    }
    data.update(overrides)
    return WorkflowBrief(**data)


def test_ecommerce_order_exception_missing_channel_blocks() -> None:
    brief = _brief(
        intent="Route ecommerce order exception cases by Shopify/Amazon channel.",
        data_sources=[],
    )

    questions = missing_fields(brief)

    assert any(q.severity == "block" and q.field_path == "data_sources" for q in questions)
    assert any("channel" in q.question.lower() for q in questions)


def test_ecommerce_faq_requires_source_citation_source() -> None:
    brief = _brief(intent="Answer ecommerce FAQ and RAG buyer questions with source citations.")

    questions = missing_fields(brief)

    assert any(q.field_path == "data_sources" and "source" in q.question.lower() for q in questions)


def test_tcm_followup_asks_source_channel_escalation_and_writeback() -> None:
    brief = _brief(
        intent="TCM followup should writeback patient message to clinic system.",
        data_sources=[],
        credentials=[],
        approval_points=[],
        success_criteria="",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="high",
            regulatory_tags=["clinical"],
            geographies=["CN"],
        ),
    )

    field_paths = {q.field_path for q in missing_fields(brief) if q.severity == "block"}

    assert {"data_sources", "credentials", "approval_points", "success_criteria"} <= field_paths


def test_tcm_patient_qa_requires_citation_disclaimer_and_human_escalation() -> None:
    brief = _brief(
        intent="Patient-facing TCM Q&A using RAG retrieval for symptoms.",
        data_sources=[],
        approval_points=[],
        compliance_boundary=ComplianceBoundary(
            pii_class_default="high",
            regulatory_tags=["clinical"],
            geographies=["CN"],
        ),
    )

    text = "\n".join(q.question.lower() for q in missing_fields(brief))

    assert "citation" in text or "source" in text
    assert "disclaimer" in text or "boundary" in text
    assert "human" in text or "review" in text


def test_missing_known_edits_is_warning() -> None:
    brief = _brief(known_edits=[])

    questions = missing_fields(brief)

    assert any(q.field_path == "known_edits" and q.severity == "warn" for q in questions)


def test_short_intent_is_warning() -> None:
    brief = _brief(intent="Short ecommerce edit.")

    questions = missing_fields(brief)

    assert any(q.field_path == "intent" and q.severity == "warn" for q in questions)


def test_complete_ecommerce_brief_has_no_blocking_questions() -> None:
    brief = _brief(
        intent="Answer ecommerce FAQ questions from product KB and policy KB with citations.",
        data_sources=[DataSourceRef(handle="product_kb", kind="kb")],
    )

    assert [q for q in missing_fields(brief) if q.severity == "block"] == []


def test_draft_missing_runtime_scope_and_compliance_are_blocking_questions() -> None:
    draft = WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with source citations.",
        trigger=TriggerSpec(mode="manual"),
        data_sources=[DataSourceRef(handle="product_kb", kind="kb")],
        success_criteria="Answer with citations.",
    )

    field_paths = {q.field_path for q in missing_fields(draft) if q.severity == "block"}

    assert {"target_runtime", "scope", "compliance_boundary"} <= field_paths


def test_complete_draft_has_no_blocking_questions() -> None:
    draft = WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with source citations.",
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

    assert [q for q in missing_fields(draft) if q.severity == "block"] == []
