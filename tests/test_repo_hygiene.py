from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_committed_customer_bindings_only_include_example_template() -> None:
    binding_names = sorted(path.name for path in (ROOT / "config" / "customers").glob("*.yaml"))

    assert binding_names == ["example.hiagent.yaml"]


def test_project_materials_do_not_reference_legacy_customer_samples() -> None:
    scanned_roots = [
        ROOT / "config",
        ROOT / "docs",
        ROOT / "loom",
        ROOT / "sow",
    ]
    matches = []
    for scanned_root in scanned_roots:
        for path in scanned_root.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".yml", ".json", ".toml"}:
                text = path.read_text(encoding="utf-8")
                if "bambu" in text.lower():
                    matches.append(path.relative_to(ROOT).as_posix())

    assert matches == []
