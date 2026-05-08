import pytest

from loom.validator.registry import Registry, RegistryEntryNotFound


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
