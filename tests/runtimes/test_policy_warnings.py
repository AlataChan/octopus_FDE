import json
from pathlib import Path

import yaml

from loom.ir.models import IRDocument, Policy, PolicyAudit, PolicyEscalation, PolicyGuardrails
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir as compile_hiagent
from loom.runtimes.hiagent.v2_6.compiler import compile_ir_chatflow

ROOT = Path(__file__).resolve().parents[2]


def _v04_policy_ir() -> IRDocument:
    base = IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )
    return base.model_copy(update={
        "ir_version": "0.4",
        "policy": Policy(
            guardrails=PolicyGuardrails(
                input_filters=["pii"],
                output_filters=["medical_advice"],
                custom_patterns=[r"(?i)password"],
            ),
            escalation=PolicyEscalation(
                confidence_min=0.7,
                confidence_from="${rerank.confidence}",
                handoff_node="out",
            ),
            audit=PolicyAudit(log_inputs=False, log_decisions=True, retention_days=90),
        ),
    })


def test_dify_lowers_guardrails_and_audit_and_warns_for_escalation():
    text, warnings = compile_dify(_v04_policy_ir())
    doc = yaml.safe_load(text)

    assert doc["workflow"]["features"]["sensitive_word_avoidance"]["enabled"] is True
    assert doc["workflow"]["features"]["sensitive_word_avoidance"]["configs"]["custom_patterns"] == [
        r"(?i)password"
    ]
    assert doc["workflow"]["audit_enabled"] is True
    assert doc["workflow"]["audit_retention_days"] == 90
    assert [warning.code for warning in warnings] == ["policy.escalation.unsupported"]
    assert warnings[0].node_id is None


def test_hiagent_persists_audit_metadata_and_warns_for_unsupported_policy_fields():
    binding = HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")
    bundle, warnings = compile_hiagent(_v04_policy_ir(), binding)
    agent = next(value for path, value in bundle.files.items() if path.startswith("agent/"))

    assert agent["AppConfig"]["AuditEnabled"] is True
    assert agent["AppConfig"]["AuditRetentionDays"] == 90
    assert {warning.code for warning in warnings} == {
        "policy.guardrails.unsupported",
        "policy.escalation.unsupported",
    }
    assert all(warning.node_id is None for warning in warnings)


def test_hiagent_chatflow_uses_same_warning_channel():
    binding = HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")
    bundle, warnings = compile_ir_chatflow(_v04_policy_ir(), binding)
    agent = next(value for path, value in bundle.files.items() if path.startswith("agent/"))

    assert agent["AppConfig"]["ChatFlowDetail"]["AuditEnabled"] is True
    assert {warning.code for warning in warnings} == {
        "policy.guardrails.unsupported",
        "policy.escalation.unsupported",
    }
