import pytest

from loom.validator.registry import Registry, RegistryEntryNotFound, content_sha


def test_load_v1():
    reg = Registry.load("v1")
    assert reg.version.startswith("sha:")  # pinned in the loader
    assert "clinic_kb" in reg.datasets
    assert reg.datasets["clinic_kb"].handle == "clinic_kb"


def test_resolve_existing_dataset():
    reg = Registry.load("v1")
    ds = reg.resolve_dataset("clinic_kb", scope="clinic/kb")
    assert ds.handle == "clinic_kb"


def test_resolve_missing_dataset():
    reg = Registry.load("v1")
    with pytest.raises(RegistryEntryNotFound):
        reg.resolve_dataset("nonexistent_kb", scope="clinic/kb")


def test_scope_acl_blocks_out_of_scope():
    reg = Registry.load("v1")
    with pytest.raises(RegistryEntryNotFound):
        reg.resolve_dataset("clinic_kb", scope="some-other-team/foo")


# ---------------------------------------------------------------------------
# H-8: content-addressed pin resolution — no more all-zero sentinel fallback.
# ---------------------------------------------------------------------------


def test_credential_entries_carry_security_binding_metadata():
    reg = Registry.load("v1")
    shopify = reg.credentials["shopify_api"]
    assert shopify.auth_scheme == "bearer"
    assert shopify.placement == "header"
    assert shopify.allowed_hosts == ("admin.shopify.com",)
    assert shopify.require_tls is True


def test_content_sha_ignores_self_declared_version_field():
    raw_a = {"version": "sha:0000000", "tools": [], "datasets": [], "credentials": []}
    raw_b = {"version": "sha:deadbeef", "tools": [], "datasets": [], "credentials": []}
    assert content_sha(raw_a) == content_sha(raw_b)


def test_content_sha_changes_when_content_changes():
    raw_a = {"version": "sha:0000000", "tools": [], "datasets": [], "credentials": []}
    raw_b = {"version": "sha:0000000", "tools": [{"handle": "t", "description": "d",
              "input_schema": {}, "output_schema": {}}], "datasets": [], "credentials": []}
    assert content_sha(raw_a) != content_sha(raw_b)


def test_content_sha_never_returns_the_old_all_zero_sentinel():
    raw = {"version": "not-a-real-sha-at-all", "tools": [], "datasets": [], "credentials": []}
    assert content_sha(raw) != "sha:0000000"
    assert content_sha(raw).startswith("sha:")
