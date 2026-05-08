import json
from pathlib import Path

from loom.fde_session.brief import (
    ApprovalPoint,
    ComplianceBoundary,
    CredentialBindingRef,
    DataSourceRef,
    InputSpec,
    TriggerSpec,
    WorkflowBrief,
)

ROOT = Path(__file__).resolve().parents[2]


def _ir(name: str) -> dict:
    return json.loads((ROOT / "examples" / "ir" / name).read_text())


def test_ecommerce_primary_brief_uses_faq_archetype_sources() -> None:
    ir = _ir("01-ecommerce-customer-faq.json")
    brief = WorkflowBrief(
        title="Ecommerce FAQ",
        intent="Answer buyer product and policy questions with source citations.",
        trigger=TriggerSpec(mode="manual"),
        inputs=[InputSpec(name="query", type="string", required=True)],
        data_sources=[
            DataSourceRef(handle="product_kb", kind="kb"),
            DataSourceRef(handle="policy_kb", kind="kb"),
        ],
        tools=["translate"],
        credentials=[],
        approval_points=[],
        success_criteria="Answer includes sources and confidence.",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="medium",
            regulatory_tags=[],
            geographies=["CN", "US", "EU"],
        ),
        known_edits=["Keep compensation language policy-bounded."],
    )

    assert brief.workflow_id is None
    assert {d.handle for d in brief.data_sources} == set(ir["registry_ref"]["datasets"])
    assert brief.tools == ir["registry_ref"]["tools"]


def test_ecommerce_order_exception_brief_models_api_credentials() -> None:
    ir = _ir("05-ecommerce-order-exception.json")
    brief = WorkflowBrief(
        workflow_id="wf-order-exception",
        title="Order Exception Triage",
        intent="Route cross-border ecommerce order exceptions by marketplace channel and SLA.",
        trigger=TriggerSpec(mode="webhook", webhook_path="/triage"),
        inputs=[
            InputSpec(name="message", type="string", required=True),
            InputSpec(name="sender_id", type="string", required=True),
        ],
        data_sources=[DataSourceRef(handle="shopify_api", kind="api")],
        tools=[],
        credentials=[
            CredentialBindingRef(
                handle="shopify_api",
                scheme="oauth2",
                allowed_hosts=["admin.shopify.com"],
            )
        ],
        approval_points=[
            ApprovalPoint(stage="refund_above_threshold", reviewer_role="cs_lead", blocking=True)
        ],
        success_criteria="Every exception receives a queue and priority.",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="medium",
            regulatory_tags=[],
            geographies=["CN", "US", "EU"],
        ),
        known_edits=["Route marketplace policy issues separately."],
    )

    assert brief.trigger.webhook_path == "/triage"
    assert {n["type"] for n in ir["nodes"]} >= {"trigger", "parallel", "condition", "output"}


def test_tcm_followup_shadow_brief_is_high_pii_with_review_gate() -> None:
    ir = _ir("04-tcm-followup.json")
    brief = WorkflowBrief(
        title="TCM Follow-up",
        intent="Prepare a staff-reviewed follow-up draft from patient history and clinic policy.",
        trigger=TriggerSpec(mode="manual"),
        inputs=[InputSpec(name="topic", type="string", required=True)],
        data_sources=[DataSourceRef(handle="patient_history", kind="dataset")],
        tools=["patient_history_lookup", "clinic_policy_lookup"],
        credentials=[],
        approval_points=[
            ApprovalPoint(stage="before_patient_message", reviewer_role="clinician", blocking=True)
        ],
        success_criteria="Draft is marked for clinician review and includes sources.",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="high",
            regulatory_tags=["clinical"],
            geographies=["CN"],
        ),
        known_edits=["No autonomous clinical advice."],
    )

    assert brief.compliance_boundary.pii_class_default == "high"
    assert {tool for tool in brief.tools} == set(ir["registry_ref"]["tools"])
