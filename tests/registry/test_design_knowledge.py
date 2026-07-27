from loom.registry.design_knowledge import DesignKnowledgeCatalog
from loom.registry.personas import PersonaCatalog
from loom.registry.templates import TemplateCatalog


def _catalog() -> DesignKnowledgeCatalog:
    return DesignKnowledgeCatalog.from_template_catalog(TemplateCatalog.load())


def test_design_knowledge_cards_project_templates_without_full_ir():
    catalog = _catalog()
    card = catalog.get("knowledge-retrieval-rag")

    assert card is not None
    payload = card.model_dump()
    assert payload["source_template_ids"] == ["knowledge-retrieval-rag"]
    assert payload["name"]["en"] == "Knowledge Retrieval (RAG)"
    assert payload["intent_summary"]
    assert payload["node_signature"] == "trigger>retrieval>llm>llm>output"
    assert payload["registry_handles"]["datasets"] == ["product_kb", "policy_kb"]
    assert "retry" in payload["policy_features"]
    assert "retrieval" in payload["required_capabilities"]
    assert "ir" not in payload


def test_design_knowledge_retrieve_filters_scope_target_and_top_k():
    catalog = _catalog()

    rows = catalog.retrieve(
        intent="retrieve knowledge base answers with citations",
        scope="ecommerce/kb",
        target="dify",
        top_k=3,
    )

    assert 1 <= len(rows) <= 3
    assert all("ecommerce/kb" in row.scopes for row in rows)
    assert all("dify" in row.compile_targets for row in rows)


def test_design_knowledge_retrieve_ranks_by_intent_against_tags_name_and_description():
    catalog = _catalog()

    rows = catalog.retrieve(
        intent="rag knowledge base sourced answer",
        scope="ecommerce/kb",
        target="dify",
        top_k=5,
    )

    assert rows
    assert rows[0].source_template_ids == ["knowledge-retrieval-rag"]


def test_design_knowledge_retrieve_diversifies_by_node_signature():
    catalog = _catalog()

    rows = catalog.retrieve(intent="", scope="ecommerce/kb", target="hiagent", top_k=10)

    assert rows
    assert len({row.node_signature for row in rows}) == len(rows)


def test_design_knowledge_retrieve_uses_persona_context_when_scope_is_open():
    catalog = _catalog()
    persona = PersonaCatalog.load().get("tcm-clinic-operator")
    assert persona is not None

    rows = catalog.retrieve(
        intent="answer patient knowledge questions with review caveat",
        target="dify",
        persona=persona,
        top_k=5,
    )

    assert rows
    assert rows[0].source_template_ids == ["medical-knowledge"]
    assert rows[0].confidence > 0.7
