from loom.fde_session.edit_intent import (
    AddComplianceDisclaimer,
    AddManualReviewGate,
    AddRetryPolicy,
    ChangeRetrievalTopK,
    ChangeTemperature,
    ChangeTriggerMode,
    MarkUnrecognized,
    parse_edit_intent,
)


def test_parse_change_trigger_mode() -> None:
    intent = parse_edit_intent("Change trigger to webhook")
    assert isinstance(intent, ChangeTriggerMode)
    assert intent.to == "webhook"


def test_parse_retrieval_top_k() -> None:
    intent = parse_edit_intent("Set retrieve top_k to 8")
    assert isinstance(intent, ChangeRetrievalTopK)
    assert intent.node_id == "retrieve"
    assert intent.to_k == 8


def test_parse_add_retry_policy() -> None:
    intent = parse_edit_intent("Add retry policy to h max_attempts 4 retry_on 5xx timeout")
    assert isinstance(intent, AddRetryPolicy)
    assert intent.node_id == "h"
    assert intent.max_attempts == 4
    assert intent.retry_on == ["5xx", "timeout"]


def test_parse_add_manual_review_gate_for_ecommerce_edit() -> None:
    intent = parse_edit_intent("Add manual review after decide_priority reviewer cs_lead")
    assert isinstance(intent, AddManualReviewGate)
    assert intent.after_node_id == "decide_priority"
    assert intent.reviewer_role == "cs_lead"


def test_parse_change_temperature() -> None:
    intent = parse_edit_intent("Change answer temperature to 0.2")
    assert isinstance(intent, ChangeTemperature)
    assert intent.node_id == "answer"
    assert intent.to == 0.2


def test_parse_add_compliance_disclaimer() -> None:
    intent = parse_edit_intent("Add compliance disclaimer to answer: Policy limits apply")
    assert isinstance(intent, AddComplianceDisclaimer)
    assert intent.node_id == "answer"
    assert intent.text == "Policy limits apply"


def test_unrecognized_edit_falls_back() -> None:
    raw = "Make it feel more premium somehow"
    intent = parse_edit_intent(raw)
    assert isinstance(intent, MarkUnrecognized)
    assert intent.raw_text == raw
