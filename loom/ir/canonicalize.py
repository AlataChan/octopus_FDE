"""Canonical IR form. Pure function. Used by Compiler, Deployer, golden tests.

Canonicalization rules (PRD §6 v0.3):
 1. Keys sorted lexicographically at every level.
 2. Default-valued fields stripped, selected by each node's own `type`.
 3. Top-level `nodes`/`edges` are order-independent and sorted by canonical
    id; `LoopNode.body` and each `ParallelNode.branches` list are NOT
    reordered — there is no separate edges list encoding their internal
    sequencing, so array position is itself semantic there.
 4. `rationale` preserved verbatim.

Changing any rule here changes every existing `canonical_ir_hash` output;
treat it as a breaking change to the drift signal and re-baseline any stored
hashes alongside the deploy.
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


def default_for(kind: str, key: str) -> tuple[bool, Any]:
    """Look up the strip default for a (kind, key) pair, if one is defined.

    Lets callers (e.g. the reviewer-facing diff) show the concrete default
    value instead of a bare "missing" when a field was stripped for hashing.
    """
    for (k, kk), default in _DEFAULT_STRIPS:
        if k == kind and kk == key:
            return True, default
    return False, None


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
        # Special-case: parallel branch *names* are order-independent, but the
        # node list within each branch is not — there is no separate edges
        # list encoding intra-branch sequencing, so array position is the
        # only signal of order (same rule as LoopNode.body below).
        if parent == "ParallelNode" and "branches" in value:
            sorted_branches = {k: value["branches"][k] for k in sorted(value["branches"].keys())}
            value["branches"] = sorted_branches
        # Recurse with proper parent label.
        out: dict[str, Any] = {}
        for k in sorted(value.keys()):
            out[k] = _canonicalize(value[k], parent=_child_kind(parent, k, value[k]))
        if parent == "IRDocument":
            # Top-level node/edge order carries no meaning by itself — actual
            # execution order comes from the edges graph — so stabilize it by
            # id instead of leaving it sensitive to input array order.
            if isinstance(out.get("nodes"), list):
                out["nodes"] = sorted(out["nodes"], key=_node_sort_key)
            if isinstance(out.get("edges"), list):
                out["edges"] = sorted(out["edges"], key=_edge_sort_key)
        return out
    if isinstance(value, list):
        return [_canonicalize(v, parent=_list_item_kind(parent, v)) for v in value]
    return value


def _list_item_kind(parent: str, item: Any) -> str:
    """Dispatch a list element to its own kind when the list holds Nodes.

    `nodes`, `LoopNode.body`, and each `ParallelNode.branches` value are all
    typed as list[Node], but by the time a list is reached here `parent` is
    only the generic "Node"/"any" marker used to select the list itself
    (see `_child_kind`). Without re-dispatching per element from its own
    `type`, per-node-kind strip rules (e.g. RetrievalNode.top_k) never match
    because the parent label seen at that point is never the specific kind.
    """
    if parent in ("Node", "any") and isinstance(item, dict) and "type" in item:
        return _node_kind(item["type"])
    return parent


def _node_sort_key(node: Any) -> str:
    if isinstance(node, dict):
        node_id = node.get("id")
        if isinstance(node_id, str):
            return node_id
    return json.dumps(node, sort_keys=True, ensure_ascii=False)


def _edge_sort_key(edge: Any) -> tuple[str, str, str, bool]:
    if not isinstance(edge, dict):
        return ("", "", json.dumps(edge, sort_keys=True, ensure_ascii=False), True)
    src = edge.get("from", edge.get("from_", ""))
    dst = edge.get("to", "")
    when = edge.get("when") or ""
    data = edge.get("data", True)
    return (str(src), str(dst), str(when), bool(data))


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
