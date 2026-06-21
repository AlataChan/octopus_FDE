from pathlib import Path

from loom.registry.personas import PersonaCatalog

ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = ROOT / "registry" / "v1" / "personas"


def test_persona_catalog_loads_all_yaml_files_as_persona_briefs():
    catalog = PersonaCatalog.load()
    rows = catalog.list()
    persona_files = sorted(PERSONAS_DIR.glob("*.yaml"))

    assert len(rows) == len(persona_files)
    assert {row.persona_id for row in rows} == {path.stem for path in persona_files}
    assert all(row.author_role for row in rows)
    assert all(row.reviewer.role for row in rows)
    assert all(row.success_criteria for row in rows)


def test_persona_catalog_gets_loaded_persona_by_id():
    catalog = PersonaCatalog.load()
    persona = catalog.get("ecommerce-operator")

    assert persona is not None
    assert persona.vertical == "ecommerce"
    assert persona.compliance_boundary.pii_class_default == "medium"
