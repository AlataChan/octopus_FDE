from unittest.mock import MagicMock, patch

from loom.planner.client import PlannerClient


def test_static_system_built_as_single_string():
    """Plan template said 2 cache breakpoints [Anthropic]; OpenAI-compatible mode uses single string."""
    with patch("loom.planner.client.OpenAI"):
        c = PlannerClient(api_key="x")
    assert isinstance(c._system_static, str)
    assert "FDE Planner" in c._system_static
    assert "IR v0.4 JSON Schema" in c._system_static
    assert "Few-shot library" in c._system_static


def test_call_appends_persona_target_registry_blocks_and_user_msg():
    with patch("loom.planner.client.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"ir_version": "0.4"}'))],
            usage=MagicMock(prompt_tokens=100, completion_tokens=50),
        )
        from loom.fde_session.persona_brief import ComplianceBoundary, PersonaBrief, ReviewerSpec
        persona = PersonaBrief(
            persona_id="ecommerce-cs-lead",
            author_role="cs_lead", vertical="ecommerce", end_user="buyer",
            reviewer=ReviewerSpec(role="ops_manager", decision_authority=["publish", "refund_above_500_USD"]),
            compliance_boundary=ComplianceBoundary(pii_class_default="medium", regulatory_tags=["GDPR", "PIPL"]),
            success_criteria="Refund flows respect monetary thresholds.",
        )
        c = PlannerClient(api_key="x")
        result = c.call(intent="do X", scope="ecommerce/ops", persona_brief=persona, target="hiagent")
        kwargs = instance.chat.completions.create.call_args.kwargs
        sys_msg = next(m for m in kwargs["messages"] if m["role"] == "system")
        user_msg = next(m for m in kwargs["messages"] if m["role"] == "user")
        # Persona, target, registry blocks all present in system text
        assert "Persona context" in sys_msg["content"]
        assert "Target runtime" in sys_msg["content"]
        assert "Declared registry" in sys_msg["content"]
        # Persona-relevant text actually filled in
        assert "ecommerce-cs-lead" in sys_msg["content"]
        assert "cs_lead" in sys_msg["content"]
        # Target injected
        assert "hiagent" in sys_msg["content"]
        # User contains intent
        assert "do X" in user_msg["content"]
        assert "Emit IR v0.4 JSON only." in user_msg["content"]
        # response parsed
        assert result.ir_text.startswith('{"ir_version"')


def test_call_default_persona_when_none():
    """Developer / debug mode without an explicit persona falls back to default-operator marker."""
    with patch("loom.planner.client.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"ir_version": "0.4"}'))],
            usage=MagicMock(prompt_tokens=100, completion_tokens=50),
        )
        c = PlannerClient(api_key="x")
        c.call(intent="do X", scope="ecommerce/kb", persona_brief=None, target="hiagent")
        kwargs = instance.chat.completions.create.call_args.kwargs
        sys_msg = next(m for m in kwargs["messages"] if m["role"] == "system")
        assert "default-operator" in sys_msg["content"]
