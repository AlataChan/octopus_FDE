"""Design-agent knowledge cards derived from the template catalog."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from loom.fde_session.persona_brief import PersonaBrief
from loom.registry.templates import LocalizedText, Target, TemplateCatalog, TemplateRecord


class RegistryHandles(BaseModel):
    tools: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    credentials: list[str] = Field(default_factory=list)


class DesignKnowledgeCard(BaseModel):
    id: str
    source_template_ids: list[str]
    name: LocalizedText
    intent_summary: str
    scopes: list[str]
    compile_targets: list[Target]
    tags: list[str]
    node_signature: str
    registry_handles: RegistryHandles
    policy_features: list[str]
    required_capabilities: list[str]
    constraints: list[str]
    anti_goals: list[str]
    confidence: float = Field(ge=0, le=1)
    rationale: str


@dataclass(frozen=True)
class _ScoredCard:
    score: int
    card: DesignKnowledgeCard


class DesignKnowledgeCatalog:
    def __init__(self, *, cards: dict[str, DesignKnowledgeCard]):
        self._cards = cards

    @classmethod
    def from_template_catalog(cls, template_catalog: TemplateCatalog) -> DesignKnowledgeCatalog:
        cards = {
            row.entry.id: _card_from_template(row)
            for row in template_catalog.list()
        }
        return cls(cards=cards)

    def list(
        self,
        *,
        scope: str | None = None,
        target: Target | None = None,
    ) -> list[DesignKnowledgeCard]:
        rows = [self._cards[key] for key in sorted(self._cards)]
        if scope:
            rows = [row for row in rows if scope in row.scopes]
        if target:
            rows = [row for row in rows if target in row.compile_targets]
        return rows

    def get(self, card_id: str) -> DesignKnowledgeCard | None:
        return self._cards.get(card_id)

    def retrieve(
        self,
        *,
        intent: str | None = None,
        scope: str | None = None,
        target: Target | None = None,
        persona: PersonaBrief | None = None,
        brief_draft: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[DesignKnowledgeCard]:
        query = " ".join(part for part in (intent, _brief_text(brief_draft), _persona_text(persona)) if part)
        scored = [
            _ScoredCard(score=_score(card, query) + _persona_score(card, persona), card=card)
            for card in self.list(scope=scope, target=target)
        ]
        scored.sort(key=lambda row: (-row.score, row.card.id))

        selected: list[DesignKnowledgeCard] = []
        seen_signatures: set[str] = set()
        for row in scored:
            if row.card.node_signature in seen_signatures:
                continue
            seen_signatures.add(row.card.node_signature)
            selected.append(_with_retrieval_confidence(row.card, row.score))
            if len(selected) >= top_k:
                break
        return selected


def _card_from_template(row: TemplateRecord) -> DesignKnowledgeCard:
    entry = row.entry
    ir = row.ir_document
    node_types = _node_types(ir.nodes)
    policy_features = _policy_features(ir.policy)
    registry_handles = RegistryHandles(
        tools=list(ir.registry_ref.tools),
        datasets=list(ir.registry_ref.datasets),
        credentials=list(ir.registry_ref.credentials),
    )
    return DesignKnowledgeCard(
        id=entry.id,
        source_template_ids=[entry.id],
        name=entry.name,
        intent_summary=ir.metadata.description or entry.description.en,
        scopes=list(entry.scopes),
        compile_targets=list(entry.compile_targets),
        tags=list(entry.tags),
        node_signature=">".join(node_types),
        registry_handles=registry_handles,
        policy_features=policy_features,
        required_capabilities=_required_capabilities(node_types),
        constraints=_constraints(ir.model_dump(by_alias=True), registry_handles),
        anti_goals=_anti_goals(node_types, entry.tags, policy_features),
        confidence=_base_confidence(policy_features, registry_handles),
        rationale=ir.metadata.rationale,
    )


def _node_types(nodes: list[Any]) -> list[str]:
    types: list[str] = []
    for node in nodes:
        node_type = str(getattr(node, "type"))
        types.append(node_type)
        if node_type == "loop":
            types.extend(_node_types(getattr(node, "body")))
        elif node_type == "parallel":
            branches = getattr(node, "branches")
            for branch_name in sorted(branches):
                types.extend(_node_types(branches[branch_name]))
    return types


def _policy_features(policy: Any) -> list[str]:
    features: list[str] = []
    for attr, label in (
        ("default_timeout_s", "timeout"),
        ("default_retry", "retry"),
        ("agent_budget", "agent_budget"),
        ("guardrails", "guardrails"),
        ("escalation", "escalation"),
        ("audit", "audit"),
    ):
        if getattr(policy, attr) is not None:
            features.append(label)
    return features


def _required_capabilities(node_types: list[str]) -> list[str]:
    mapping = {
        "trigger": "trigger",
        "retrieval": "retrieval",
        "llm": "llm_generation",
        "http": "http_integration",
        "code": "code_execution",
        "condition": "branching",
        "loop": "iteration",
        "parallel": "parallel_execution",
        "agent": "agent_tool_use",
        "output": "structured_output",
    }
    return sorted({mapping[node_type] for node_type in node_types if node_type in mapping})


def _constraints(raw_ir: dict[str, Any], registry_handles: RegistryHandles) -> list[str]:
    constraints: list[str] = []
    for item in raw_ir.get("inputs", []):
        if isinstance(item, dict) and item.get("required"):
            constraints.append(f"requires_input:{item.get('name')}")
    constraints.extend(f"requires_tool:{handle}" for handle in registry_handles.tools)
    constraints.extend(f"requires_dataset:{handle}" for handle in registry_handles.datasets)
    constraints.extend(f"requires_credential:{handle}" for handle in registry_handles.credentials)
    if not constraints:
        constraints.append("no_external_registry_handle_required")
    return constraints


def _anti_goals(node_types: list[str], tags: list[str], policy_features: list[str]) -> list[str]:
    anti_goals: list[str] = []
    tag_set = {tag.lower() for tag in tags}
    if "retrieval" not in node_types:
        anti_goals.append("not_for_source_grounded_answering_without_added_retrieval")
    if "http" not in node_types:
        anti_goals.append("not_for_live_backend_mutation_without_integration_nodes")
    if tag_set.intersection({"medical", "legal", "compliance"}) and "escalation" not in policy_features:
        anti_goals.append("not_for_autonomous_regulated_decisions_without_review")
    if not anti_goals:
        anti_goals.append("not_a_complete_production_workflow_without_persona_constraints")
    return anti_goals


def _base_confidence(policy_features: list[str], registry_handles: RegistryHandles) -> float:
    confidence = 0.68
    if policy_features:
        confidence += 0.08
    if registry_handles.tools or registry_handles.datasets or registry_handles.credentials:
        confidence += 0.04
    return min(confidence, 0.9)


def _with_retrieval_confidence(card: DesignKnowledgeCard, score: int) -> DesignKnowledgeCard:
    confidence = min(0.95, card.confidence + min(score, 10) * 0.01)
    return card.model_copy(update={"confidence": confidence})


def _score(card: DesignKnowledgeCard, query: str | None) -> int:
    tokens = _tokens(query or "")
    if not tokens:
        return 0
    tag_text = " ".join(card.tags).lower()
    name_text = f"{card.name.zh} {card.name.en}".lower()
    description_text = card.intent_summary.lower()
    score = 0
    for token in tokens:
        if token in {tag.lower() for tag in card.tags}:
            score += 4
        if token in name_text:
            score += 3
        if token in description_text:
            score += 2
        if token in tag_text:
            score += 1
    return score


def _persona_score(card: DesignKnowledgeCard, persona: PersonaBrief | None) -> int:
    if persona is None:
        return 0

    score = 0
    scope_prefix = _vertical_scope_prefix(persona.vertical)
    if scope_prefix and any(scope.startswith(scope_prefix) for scope in card.scopes):
        score += 8

    persona_tokens = set(_tokens(_persona_text(persona)))
    card_text = " ".join([
        card.id,
        card.name.zh,
        card.name.en,
        card.intent_summary,
        " ".join(card.tags),
        " ".join(card.scopes),
        " ".join(card.registry_handles.datasets),
        " ".join(card.policy_features),
        " ".join(card.required_capabilities),
        " ".join(card.constraints),
        " ".join(card.anti_goals),
    ]).lower()
    score += sum(2 for token in persona_tokens if token in card_text)

    regulatory_tags = {tag.lower() for tag in persona.compliance_boundary.regulatory_tags}
    if persona.compliance_boundary.pii_class_default in {"medium", "high"}:
        if "guardrails" in card.policy_features or "compliance" in {tag.lower() for tag in card.tags}:
            score += 3
    if regulatory_tags and ("guardrails" in card.policy_features or "audit" in card.policy_features):
        score += 2
    if persona.reviewer.decision_authority and (
        "escalation" in card.policy_features or "condition" in card.node_signature
    ):
        score += 1
    return score


def _persona_text(persona: PersonaBrief | None) -> str:
    if persona is None:
        return ""
    return " ".join([
        persona.persona_id,
        persona.author_role,
        persona.vertical,
        persona.end_user,
        persona.reviewer.role,
        " ".join(persona.reviewer.decision_authority),
        persona.compliance_boundary.pii_class_default,
        " ".join(persona.compliance_boundary.regulatory_tags),
        " ".join(persona.compliance_boundary.geographies),
        persona.success_criteria,
    ])


def _vertical_scope_prefix(vertical: str) -> str | None:
    if vertical == "tcm_clinic":
        return "clinic/"
    if vertical == "ecommerce":
        return "ecommerce/"
    return None


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower()) if len(token) > 1]


def _brief_text(brief_draft: dict[str, Any] | None) -> str:
    if not brief_draft:
        return ""
    values: list[str] = []
    for value in brief_draft.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value if isinstance(item, str))
    return " ".join(values)
