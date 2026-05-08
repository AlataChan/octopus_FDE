import pytest
from pydantic import ValidationError

from loom.fde_session.persona_brief import ComplianceBoundary, PersonaBrief, ReviewerSpec
from loom.planner.types import IntentRequest, PlannerResult


def test_intent_request_minimum():
    r = IntentRequest(
        intent="Build an ecommerce customer-FAQ workflow that answers buyer questions from the product/policy KB with citations and escalation on low confidence.",
        scope="ecommerce/kb",
        max_retries=3,
    )
    assert r.intent.startswith("Build")


def test_intent_request_rejects_missing_scope():
    with pytest.raises(ValidationError):
        IntentRequest(intent="...", max_retries=3)  # type: ignore[call-arg]


def test_planner_result_carries_attempts_and_failure_taxonomy():
    pr = PlannerResult(
        ir=None,
        attempts=3,
        ok=False,
        failures=[{"bucket": "schema", "detail": "missing rationale"}],
        cost_usd=0.18,
        latency_s=42.5,
    )
    assert pr.attempts == 3
    assert pr.failures[0].bucket == "schema"


def test_intent_request_with_persona_brief():
    persona = PersonaBrief(
        persona_id="ecommerce-operator",
        author_role="operator",
        vertical="ecommerce",
        end_user="buyer",
        reviewer=ReviewerSpec(role="cs_supervisor", decision_authority=["publish"]),
        compliance_boundary=ComplianceBoundary(
            pii_class_default="medium",
            regulatory_tags=["GDPR", "PIPL"],
            geographies=["CN", "US"],
        ),
        success_criteria="Buyers receive accurate replies.",
    )
    r = IntentRequest(
        intent="Build an ecommerce FAQ workflow.",
        scope="ecommerce/kb",
        persona_brief=persona,
    )
    assert r.persona_brief == persona
    assert r.persona_brief is not None
    assert r.persona_brief.persona_id == "ecommerce-operator"


def test_intent_request_default_target_is_hiagent():
    r = IntentRequest(
        intent="Build an ecommerce FAQ workflow.",
        scope="ecommerce/kb",
    )
    assert r.target == "hiagent"
