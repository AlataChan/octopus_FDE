from pathlib import Path

import yaml

from loom.fde_session.persona_brief import ComplianceBoundary, PersonaBrief, ReviewerSpec

ROOT = Path(__file__).resolve().parents[2]
PERSONAS = ROOT / "registry" / "v1" / "personas"


def test_persona_brief_minimum():
    p = PersonaBrief(
        persona_id="ecommerce-operator",
        author_role="operator",
        vertical="ecommerce",
        end_user="buyer",
        reviewer=ReviewerSpec(role="cs_supervisor", decision_authority=["publish"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="medium",
                                                regulatory_tags=["GDPR", "PIPL"],
                                                geographies=["CN", "US"]),
        success_criteria="Buyers receive accurate, channel-appropriate replies.",
    )
    assert p.compliance_boundary.pii_class_default == "medium"


def test_high_pii_persona_default():
    """TCM persona must default to high pii_class."""
    p = PersonaBrief(
        persona_id="tcm-clinic-operator",
        author_role="operator",
        vertical="tcm_clinic",
        end_user="patient",
        reviewer=ReviewerSpec(role="clinician", decision_authority=["publish", "medical_response_approval"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="high",
                                                regulatory_tags=["PIPL", "PIPL-medical"]),
        success_criteria="No diagnosis or prescription auto-published.",
    )
    assert p.compliance_boundary.pii_class_default == "high"


def test_seed_personas_load_from_yaml() -> None:
    personas = []
    for path in sorted(PERSONAS.glob("*.yaml")):
        personas.append(PersonaBrief.model_validate(yaml.safe_load(path.read_text())))

    assert {p.persona_id for p in personas} == {
        "ecommerce-operator",
        "ecommerce-cs-lead",
        "tcm-clinic-operator",
    }
    assert len(personas) == 3


def test_compliance_boundary_default_pii() -> None:
    boundary = ComplianceBoundary()

    assert boundary.pii_class_default == "low"
