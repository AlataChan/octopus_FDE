"""Canonical IR form. Pure function. Used by Compiler, Deployer, golden tests.

Canonicalization rules (PRD §6 v0.3):
 1. Keys sorted lexicographically at every level.
 2. Default-valued fields stripped.
 3. Order-independent compounds sorted by canonical id.
 4. `rationale` preserved verbatim.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, cast

# Default values that get stripped at canonicalization time. Keep this list in
# sync with the v0.3 schema's `default` declarations.
_DEFAULT_STRIPS: list[tuple[tuple[str, ...], Any]] = [
    (("Edge", "data"), True),
    (("RetrievalNode", "top_k"), 5),
    (("RetrievalNode", "rerank"), False),
    (("PortDecl", "required"), False),
    (("Retry", "backoff"), "exponential"),
]


def canonical_ir(doc: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical form of an IR document."""
    return cast("dict[str, Any]", _canonicalize(deepcopy(doc), parent="IRDocument"))


def canonical_ir_hash(doc: dict[str, Any]) -> str:
    """SHA-256 hex of the canonical IR's JSON serialization."""
    canon = canonical_ir(doc)
    payload = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonicalize(value: Any, *, parent: str) -> Any:
    if isinstance(value, dict):
        # Strip defaults for this parent.
        for (kind, key), default in _DEFAULT_STRIPS:
            if kind == parent and value.get(key) == default:
                value.pop(key, None)
        # Special-case: parallel branches are order-independent.
        if parent == "ParallelNode" and "branches" in value:
            sorted_branches = {k: value["branches"][k] for k in sorted(value["branches"].keys())}
            value["branches"] = sorted_branches
        # Recurse with proper parent label.
        out: dict[str, Any] = {}
        for k in sorted(value.keys()):
            out[k] = _canonicalize(value[k], parent=_child_kind(parent, k, value[k]))
        return out
    if isinstance(value, list):
        return [_canonicalize(v, parent=parent) for v in value]
    return value


def _child_kind(parent: str, key: str, value: Any) -> str:
    """Return a canonical kind string for child dispatch.

    Exhaustively listed so default stripping stays predictable. Keep in sync
    with schemas/ir-v0.3.schema.json.
    """
    if parent == "IRDocument":
        return {
            "metadata": "Metadata",
            "registry_ref": "RegistryRef",
            "policy": "Policy",
            "inputs": "PortDecl",
            "outputs": "PortDecl",
            "nodes": "Node",
            "edges": "Edge",
        }.get(key, "any")
    if parent == "Node" or parent == "any":
        if isinstance(value, dict) and "type" in value:
            return _node_kind(value["type"])
        return "any"
    if parent == "LoopNode" and key == "body":
        return "Node"
    if parent == "ParallelNode" and key == "branches":
        return "any"  # branches are dict[str, list[Node]]; recurse keys then list-of-nodes
    if parent.endswith("Node") and key == "retry":
        return "Retry"
    if parent.endswith("Node") and key == "branches":
        return "ConditionBranch"
    if parent == "Policy" and key == "default_retry":
        return "Retry"
    if parent == "Policy" and key == "agent_budget":
        return "AgentBudget"
    return "any"


def _node_kind(node_type: str) -> str:
    return {
        "trigger": "TriggerNode", "llm": "LLMNode", "retrieval": "RetrievalNode",
        "http": "HTTPNode", "code": "CodeNode", "condition": "ConditionNode",
        "loop": "LoopNode", "parallel": "ParallelNode", "agent": "AgentNode",
        "output": "OutputNode",
    }.get(node_type, "any")
