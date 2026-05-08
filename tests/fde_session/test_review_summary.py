from loom.fde_session.review_summary import (
    ComplianceChange,
    CredentialChange,
    ExternalCall,
    NodeChange,
    PolicyChange,
    ReviewSummary,
)


def test_review_summary_flags_credential_expansion_and_customer_data_access() -> None:
    summary = ReviewSummary(
        node_changes=[NodeChange(node_id="h", kind="modified", field_diffs=["url widened"])],
        credential_access_changes=[
            CredentialChange(handle="shopify_api", kind="scope_widened")
        ],
        external_calls=[
            ExternalCall(
                node_id="h",
                host="admin.shopify.com",
                method="POST",
                sensitivity="write",
            )
        ],
        policy_changes=[],
        compliance_changes=[
            ComplianceChange(field="pii_class_default", before="low", after="medium")
        ],
        reverse_compile_status="drift_detected",
    )

    assert summary.credential_access_changes[0].kind == "scope_widened"
    assert summary.external_calls[0].sensitivity == "write"


def test_review_summary_accepts_patient_data_access_review() -> None:
    summary = ReviewSummary(
        node_changes=[],
        credential_access_changes=[],
        external_calls=[
            ExternalCall(
                node_id="patient_history_lookup",
                host="clinic.example.internal",
                method="GET",
                sensitivity="read",
            )
        ],
        policy_changes=[
            PolicyChange(field="approval_points", before="none", after="clinician")
        ],
        compliance_changes=[
            ComplianceChange(field="regulatory_tags", before="[]", after="[clinical]")
        ],
        reverse_compile_status="blocked",
    )

    assert summary.reverse_compile_status == "blocked"
    assert summary.policy_changes[0].field == "approval_points"


def test_review_summary_defaults_to_empty_lists() -> None:
    summary = ReviewSummary(reverse_compile_status="clean")

    assert summary.node_changes == []
    assert summary.credential_access_changes == []
    assert summary.external_calls == []
    assert summary.policy_changes == []
    assert summary.compliance_changes == []
