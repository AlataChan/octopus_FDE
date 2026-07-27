import json

import pytest

import loom.fde_session.planner_payload as planner_payload
from loom.fde_session.brief import (
    ApprovalPoint,
    ComplianceBoundary,
    CredentialBindingRef,
    DataSourceRef,
    InputSpec,
    TriggerSpec,
    WorkflowBriefDraft,
)
from loom.fde_session.planner_payload import (
    PlannerPayloadBlocked,
    prepare_outbound_planner_payload,
)


def test_email_in_intent_blocks_outbound_planner_payload() -> None:
    with pytest.raises(PlannerPayloadBlocked) as raised:
        prepare_outbound_planner_payload(
            intent="Build a follow-up workflow for patient@clinic.cn",
        )

    assert raised.value.field_path == "intent"
    assert raised.value.category == "email"


@pytest.mark.parametrize(
    ("marker", "category"),
    [
        ("sk-abcdefghijklmnopqrst", "secret"),
        ("[REDACTED]", "secret"),
        ("13812345678", "cn_mobile"),
        ("110101199003072316", "cn_resident_id"),
        ("6222021234567890", "long_digit_run"),
    ],
)
def test_sensitive_marker_in_intent_blocks_with_category(
    marker: str,
    category: str,
) -> None:
    with pytest.raises(PlannerPayloadBlocked) as raised:
        prepare_outbound_planner_payload(intent=f"Build a workflow for {marker}")

    assert raised.value.field_path == "intent"
    assert raised.value.category == category


def test_detector_failure_blocks_outbound_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_detector(_text: str) -> None:
        raise RuntimeError("detector unavailable")

    monkeypatch.setattr(
        planner_payload,
        "_detect_sensitive_category",
        broken_detector,
    )

    with pytest.raises(PlannerPayloadBlocked) as raised:
        prepare_outbound_planner_payload(intent="Build a clean FAQ workflow")

    assert raised.value.field_path == "intent"
    assert raised.value.category == "detector_error"


def test_draft_outbound_string_contains_only_allowed_brief_fields() -> None:
    intent = "Build a scheduled TCM knowledge workflow."
    draft = WorkflowBriefDraft(
        workflow_id="drop-workflow-id",
        title="DROP-TITLE",
        intent=intent,
        trigger=TriggerSpec(mode="schedule", schedule_cron="0 9 * * *"),
        inputs=[
            InputSpec(
                name="question",
                type="string",
                required=True,
                description="DROP-INPUT-DESCRIPTION",
            )
        ],
        data_sources=[DataSourceRef(handle="tcm_kb", kind="kb")],
        tools=["retrieve_tcm_knowledge"],
        credentials=[
            CredentialBindingRef(
                handle="tcm_api",
                scheme="bearer",
                allowed_hosts=["api.tcm.example"],
            )
        ],
        approval_points=[
            ApprovalPoint(
                stage="clinical_review",
                reviewer_role="licensed_practitioner",
                blocking=True,
            )
        ],
        success_criteria="DROP-SUCCESS-CRITERIA",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="high",
            regulatory_tags=["PIPL", "PIPL-medical"],
            geographies=["CN"],
        ),
        intent_clarifications=["DROP-INTENT-CLARIFICATION"],
        known_edits=["DROP-KNOWN-EDIT"],
        target_runtime="hiagent",
        scope="tcm/clinic",
    )

    outbound = prepare_outbound_planner_payload(
        intent=intent,
        brief=draft,
    ).user_message

    heading = "\n\n# Workflow brief draft\n"
    assert outbound.startswith(intent + heading)
    serialized = json.loads(outbound.split(heading, maxsplit=1)[1])
    assert serialized == {
        "approval_points": [
            {
                "blocking": True,
                "reviewer_role": "licensed_practitioner",
                "stage": "clinical_review",
            }
        ],
        "compliance_boundary": {
            "geographies": ["CN"],
            "pii_class_default": "high",
            "regulatory_tags": ["PIPL", "PIPL-medical"],
        },
        "credentials": [
            {
                "allowed_hosts": ["api.tcm.example"],
                "handle": "tcm_api",
                "scheme": "bearer",
            }
        ],
        "data_sources": [{"handle": "tcm_kb", "kind": "kb"}],
        "inputs": [{"name": "question", "required": True, "type": "string"}],
        "intent": intent,
        "scope": "tcm/clinic",
        "target_runtime": "hiagent",
        "tools": ["retrieve_tcm_knowledge"],
        "trigger": {
            "mode": "schedule",
            "schedule_cron": "0 9 * * *",
        },
    }
    for dropped_marker in (
        "drop-workflow-id",
        "DROP-TITLE",
        "DROP-INPUT-DESCRIPTION",
        "DROP-SUCCESS-CRITERIA",
        "DROP-INTENT-CLARIFICATION",
        "DROP-KNOWN-EDIT",
    ):
        assert dropped_marker not in outbound


def test_edit_outbound_string_and_context_share_sanitized_workflow_brief() -> None:
    draft = WorkflowBriefDraft(
        title="DROP-EDIT-TITLE",
        intent="Build a clean FAQ workflow.",
        inputs=[
            InputSpec(
                name="question",
                type="string",
                description="DROP-EDIT-INPUT-DESCRIPTION",
            )
        ],
        success_criteria="DROP-EDIT-SUCCESS",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=["CN"],
        ),
        target_runtime="hiagent",
        scope="ecommerce/kb",
    )
    context = {
        "base_ir_sha256": "abc123",
        "current_ir": {"metadata": {"name": "faq"}},
        "workflow_brief": draft.model_dump(mode="json"),
    }

    prepared = prepare_outbound_planner_payload(
        intent="Add manual review after retrieval.",
        extra_context=context,
    )

    assert prepared.extra_context is not None
    assert prepared.extra_context["base_ir_sha256"] == "abc123"
    safe_brief = prepared.extra_context["workflow_brief"]
    assert isinstance(safe_brief, dict)
    assert safe_brief["intent"] == "Build a clean FAQ workflow."
    assert safe_brief["inputs"] == [
        {"name": "question", "required": False, "type": "string"}
    ]
    assert "DROP-EDIT-TITLE" not in prepared.user_message
    assert "DROP-EDIT-INPUT-DESCRIPTION" not in prepared.user_message
    assert "DROP-EDIT-SUCCESS" not in prepared.user_message
    assert "# Existing workflow context" in prepared.user_message
    assert '"base_ir_sha256": "abc123"' in prepared.user_message


def test_nested_workflow_brief_intent_is_checked_before_edit_egress() -> None:
    detected_value = "patient@clinic.cn"
    draft = WorkflowBriefDraft(
        intent=f"Build a follow-up workflow for {detected_value}",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="high",
            regulatory_tags=["PIPL"],
            geographies=["CN"],
        ),
    )

    with pytest.raises(PlannerPayloadBlocked) as raised:
        prepare_outbound_planner_payload(
            intent="Add manual review after retrieval.",
            extra_context={
                "workflow_brief": draft.model_dump(mode="json"),
            },
        )

    assert raised.value.field_path == "workflow_brief.intent"
    assert raised.value.category == "email"
