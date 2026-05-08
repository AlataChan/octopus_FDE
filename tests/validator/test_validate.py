import json
from pathlib import Path

from loom.validator.validate import validate

ROOT = Path(__file__).resolve().parents[2]


def test_clean_ecommerce_faq_archetype_passes():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="ecommerce/kb")
    assert failures == [], failures


def test_missing_rationale_caught_as_schema_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["nodes"][1]["rationale"]
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "schema" for f in failures)


def test_unknown_var_ref_caught_as_reference_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    # rerank prompt references ${nonexistent.x}
    doc["nodes"][2]["prompt"] = "Bad ref ${nonexistent.x}"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" for f in failures)


def test_out_of_scope_dataset_caught_as_registry_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="some-other-team/foo")
    # product_kb / policy_kb are scoped to ecommerce/kb — out-of-scope here
    assert any(f.bucket == "policy" or f.bucket == "reference" for f in failures), failures
