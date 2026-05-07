import json
from pathlib import Path

import pytest

from loom.ir.schema import validate

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_DIR = ROOT / "examples" / "ir"
SOW_DIR = ROOT / "examples" / "ir" / "sow"


def _archetypes(d: Path) -> list[Path]:
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file())


@pytest.mark.parametrize("path", _archetypes(PLACEHOLDER_DIR), ids=lambda p: p.name)
def test_placeholder_archetype_validates(path: Path):
    doc = json.loads(path.read_text())
    validate(doc)


@pytest.mark.parametrize("path", _archetypes(SOW_DIR), ids=lambda p: p.name)
def test_sow_archetype_validates(path: Path):
    doc = json.loads(path.read_text())
    validate(doc)


def test_archetype_node_count_within_25(tmp_path):
    """PRD §7 Phase 0 gate: each archetype ≤25 nodes."""
    for p in _archetypes(SOW_DIR) or _archetypes(PLACEHOLDER_DIR):
        doc = json.loads(p.read_text())
        n = _count_nodes(doc["nodes"])
        assert n <= 25, f"{p.name} has {n} nodes (limit 25)"


def _count_nodes(nodes):
    total = 0
    for n in nodes:
        total += 1
        if n["type"] == "loop":
            total += _count_nodes(n["body"])
        elif n["type"] == "parallel":
            for branch in n["branches"].values():
                total += _count_nodes(branch)
    return total
