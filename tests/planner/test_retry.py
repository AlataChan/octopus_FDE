import json
from pathlib import Path

from loom.planner.client import CallResult
from loom.planner.retry import plan
from loom.planner.types import IntentRequest

ROOT = Path(__file__).resolve().parents[2]


def _good_ir_text():
    return (ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()


def _bad_ir_text():
    doc = json.loads(_good_ir_text())
    del doc["nodes"][1]["rationale"]
    return json.dumps(doc)


class _FakeClient:
    def __init__(self, sequence):
        self._sequence = list(sequence)
        self.calls = 0
        self.last_kwargs: dict | None = None

    def call(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return CallResult(ir_text=self._sequence.pop(0), cost_usd=0.05, latency_s=0.1)


def test_intent_request_passes_persona_and_target_through_to_client():
    """Persona Brief + target on IntentRequest must reach PlannerClient.call."""
    from loom.fde_session.persona_brief import ComplianceBoundary, PersonaBrief, ReviewerSpec
    persona = PersonaBrief(
        persona_id="tcm-clinic-operator",
        author_role="operator", vertical="tcm_clinic", end_user="patient",
        reviewer=ReviewerSpec(role="clinician", decision_authority=["publish", "medical_response_approval"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="high", regulatory_tags=["PIPL", "PIPL-medical"]),
        success_criteria="No diagnosis or prescription auto-published.",
    )
    fc = _FakeClient([_good_ir_text()])
    req = IntentRequest(
        intent="x", scope="ecommerce/kb",
        persona_brief=persona, target="dify", max_retries=3,
    )
    plan(req, client=fc)
    assert fc.last_kwargs is not None
    assert fc.last_kwargs["persona_brief"] is persona
    assert fc.last_kwargs["target"] == "dify"


def test_first_try_pass():
    fc = _FakeClient([_good_ir_text()])
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert res.ok and res.attempts == 1
    assert fc.calls == 1


def test_self_correction_on_second_try():
    fc = _FakeClient([_bad_ir_text(), _good_ir_text()])
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert res.ok and res.attempts == 2


def test_gives_up_after_max_retries():
    fc = _FakeClient([_bad_ir_text()] * 4)
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert not res.ok and res.attempts == 4
    assert any(f.bucket == "schema" for f in res.failures)
