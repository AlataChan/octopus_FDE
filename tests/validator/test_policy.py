import json
from pathlib import Path

from loom.ir.models import IRDocument
from loom.validator.policy import _check_python_sandbox, check_policy

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq():
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()))


def _v04_faq(**policy_updates):
    from loom.ir.models import Policy

    base = _ecommerce_faq()
    policy = Policy(**policy_updates)
    return base.model_copy(update={"ir_version": "0.4", "policy": policy})


def test_clean_archetype_has_no_policy_failures():
    failures = check_policy(_ecommerce_faq())
    assert failures == []


def test_node_timeout_cannot_exceed_workflow_default():
    ir = _ecommerce_faq().model_copy(update={
        "policy": _ecommerce_faq().policy.model_copy(update={"default_timeout_s": 10}),
    })
    # mutate one node to exceed default
    nodes = list(ir.nodes)
    nodes[1] = nodes[1].model_copy(update={"timeout_s": 30})  # retrieve.timeout_s = 30 > 10
    ir = ir.model_copy(update={"nodes": nodes})
    failures = check_policy(ir)
    assert any(f.bucket == "policy" and "timeout_s" in f.detail for f in failures)


def test_agent_fallback_requires_existing_node():
    # The `01-ecommerce-customer-faq` archetype has no agent. Build a minimal agent IR programmatically
    # in this test for clarity.
    from loom.ir.models import (
        AgentBudget,
        AgentNode,
        Edge,
        Metadata,
        OutputNode,
        Policy,
        PortDecl,
        RegistryRef,
        TriggerNode,
    )
    ir = IRDocument(
        ir_version="0.3",
        metadata=Metadata(name="agent-fb", owner="o", rationale="r"),
        registry_ref=RegistryRef(registry_version="sha:0000000", tools=["t1"]),
        policy=Policy(),
        inputs=[], outputs=[PortDecl(name="x", type="string")],
        nodes=[
            TriggerNode(id="s", type="trigger", mode="manual", rationale="r"),
            AgentNode(
                id="a", type="agent", model="m", tools=["t1"],
                input_schema={"type": "object"}, output_schema={"type": "object"},
                budget=AgentBudget(max_iterations=1, max_tokens=1000, max_wall_clock_s=5),
                on_budget_exhausted="fallback", fallback_edge="missing",
                rationale="r",
            ),
            OutputNode(id="o", type="output", bindings={"x": "${a.x}"}, rationale="r"),
        ],
        edges=[Edge(**{"from": "s"}, to="a"), Edge(**{"from": "a"}, to="o")],
    )
    failures = check_policy(ir)
    assert any("fallback_edge" in f.detail for f in failures)


def test_v04_guardrails_custom_patterns_must_compile():
    from loom.ir.models import PolicyGuardrails

    ir = _v04_faq(guardrails=PolicyGuardrails(custom_patterns=["["]))
    failures = check_policy(ir)
    assert any("valid regex" in f.detail for f in failures)


def test_v04_escalation_handoff_node_must_be_output():
    from loom.ir.models import PolicyEscalation

    ir = _v04_faq(
        escalation=PolicyEscalation(
            confidence_min=0.7,
            confidence_from="${rerank.confidence}",
            handoff_node="answer",
        )
    )
    failures = check_policy(ir)
    assert any("handoff_node" in f.detail and "output node" in f.detail for f in failures)


def test_v04_escalation_confidence_from_must_reference_numeric_llm_schema_field():
    from loom.ir.models import PolicyEscalation

    ir = _v04_faq(
        escalation=PolicyEscalation(
            confidence_min=0.7,
            confidence_from="${answer.answer}",
            handoff_node="out",
        )
    )
    failures = check_policy(ir)
    assert any("must be numeric" in f.detail for f in failures)


def test_v04_escalation_valid_confidence_ref_passes():
    from loom.ir.models import PolicyEscalation

    ir = _v04_faq(
        escalation=PolicyEscalation(
            confidence_min=0.7,
            confidence_from="${rerank.confidence}",
            handoff_node="out",
        )
    )
    assert check_policy(ir) == []


def test_v04_audit_retention_cannot_exceed_org_cap():
    from loom.ir.models import PolicyAudit

    ir = _v04_faq(audit=PolicyAudit(log_decisions=True, retention_days=366))
    failures = check_policy(ir, audit_max_retention_days=365)
    assert any("retention_days" in f.detail and "org cap" in f.detail for f in failures)


# ---------------------------------------------------------------------------
# H-3: code sandbox — AST/import allowlist.
# ---------------------------------------------------------------------------


def _ir_with_code(source: str, *, language: str = "python"):
    from loom.ir.models import (
        CodeNode,
        Edge,
        Metadata,
        OutputNode,
        Policy,
        PortDecl,
        RegistryRef,
        TriggerNode,
    )

    return IRDocument(
        ir_version="0.3",
        metadata=Metadata(name="code-sandbox", owner="o", rationale="r"),
        registry_ref=RegistryRef(registry_version="sha:0000000"),
        policy=Policy(),
        inputs=[], outputs=[PortDecl(name="x", type="string")],
        nodes=[
            TriggerNode(id="s", type="trigger", mode="manual", rationale="r"),
            CodeNode(id="c", type="code", language=language, source=source, rationale="r"),
            OutputNode(id="o", type="output", bindings={"x": "${c.x}"}, rationale="r"),
        ],
        edges=[Edge(**{"from": "s"}, to="c"), Edge(**{"from": "c"}, to="o")],
    )


def test_code_node_dangerous_import_rejected():
    ir = _ir_with_code("import os\nreturn {'x': os.getcwd()}")
    failures = check_policy(ir)
    assert any("import 'os'" in f.detail and "sandbox allowlist" in f.detail for f in failures)


def test_code_node_dangerous_call_rejected():
    ir = _ir_with_code("return {'x': eval(inputs['expr'])}")
    failures = check_policy(ir)
    assert any("'eval'" in f.detail and "forbidden" in f.detail for f in failures)


def test_canonical_hiagent_handler_input_parameter_passes_sandbox():
    source = (
        'def handler(input=""):\n'
        "    params = input if isinstance(input, dict) else {}\n"
        '    return {"a": params.get("q", "")}\n'
    )

    assert _check_python_sandbox(source) == []


def test_unshadowed_input_builtin_is_rejected():
    reasons = _check_python_sandbox('input("give me stdin")')

    assert any("reference to 'input' is forbidden" in reason for reason in reasons)


def test_aliasing_eval_builtin_is_rejected():
    reasons = _check_python_sandbox('f = eval\nf("1 + 1")')

    assert any("reference to 'eval' is forbidden" in reason for reason in reasons)


def test_function_local_bindings_shadow_dangerous_builtins():
    sources = [
        (
            "def handler(value):\n"
            "    open = value\n"
            '    return open("file.txt")\n'
        ),
        (
            "def handler(callables):\n"
            "    for exec in callables:\n"
            '        exec("payload")\n'
        ),
        (
            "def handler(context):\n"
            "    with context as compile:\n"
            '        return compile("source")\n'
        ),
        (
            "def handler():\n"
            "    import json as eval\n"
            "    return eval.dumps({})\n"
        ),
    ]

    for source in sources:
        assert _check_python_sandbox(source) == []


def test_comprehension_target_only_shadows_inside_comprehension():
    source = (
        "def handler(values):\n"
        "    shadowed = [input for input in values]\n"
        '    return input("give me stdin")\n'
    )

    reasons = _check_python_sandbox(source)

    assert reasons == ["reference to 'input' is forbidden in a sandboxed code node"]


def test_nested_function_closes_over_dangerous_name_binding():
    source = (
        "def outer(input):\n"
        "    def inner():\n"
        "        return input\n"
        "    return inner()\n"
    )

    assert _check_python_sandbox(source) == []


def test_function_parameter_does_not_shadow_module_builtin_reference():
    source = (
        "def handler(input):\n"
        "    return input\n"
        'input("give me stdin")\n'
    )

    reasons = _check_python_sandbox(source)

    assert reasons == ["reference to 'input' is forbidden in a sandboxed code node"]


def test_code_node_allowlisted_import_passes():
    ir = _ir_with_code("import json\nreturn {'x': json.dumps({})}")
    failures = check_policy(ir)
    assert not any("sandbox" in f.detail or "forbidden" in f.detail for f in failures)


def test_js_code_node_dangerous_pattern_rejected():
    ir = _ir_with_code("const r = await fetch(url); return {x: r};", language="javascript")
    failures = check_policy(ir)
    assert any("forbidden pattern" in f.detail for f in failures)


def test_code_node_subclasses_sandbox_escape_rejected():
    # Classic Python sandbox-escape chain: reaches arbitrary builtins via
    # object introspection without importing anything or naming a blocked
    # root (`().__class__` starts from a literal, not an `os`/`sys`/... name).
    ir = _ir_with_code(
        "x = ().__class__.__bases__[0].__subclasses__()\nreturn {'x': str(x)}"
    )
    failures = check_policy(ir)
    assert any(
        "'__subclasses__'" in f.detail and "introspection" in f.detail for f in failures
    ), failures
    assert any("'__bases__'" in f.detail for f in failures), failures
    assert any("'__class__'" in f.detail for f in failures), failures


# ---------------------------------------------------------------------------
# Dynamic attribute/namespace access.
#
# The attribute-name checks above only see `ast.Attribute` nodes. Every builtin
# that reaches an attribute or a namespace *dynamically* produces an `ast.Call`
# instead, so it walks straight past them. `getattr(object, "__subcl" +
# "asses__")()` reconstructs the escape chain above with no `ast.Attribute` node
# anywhere in the tree.
#
# Names that cannot be resolved statically are rejected: the checker cannot
# prove them safe, so it fails closed.
# ---------------------------------------------------------------------------


def test_getattr_with_computed_attribute_name_is_rejected():
    source = (
        'def handler(input=""):\n'
        '    c = getattr(object, "__subcl" + "asses__")()\n'
        "    return {}\n"
    )

    reasons = _check_python_sandbox(source)

    assert any("getattr" in reason for reason in reasons), reasons


def test_getattr_with_dangerous_literal_attribute_name_is_rejected():
    source = 'def handler(input=""):\n    return {"a": getattr(object, "__subclasses__")}\n'

    reasons = _check_python_sandbox(source)

    assert any("__subclasses__" in reason for reason in reasons), reasons


def test_getattr_with_safe_literal_attribute_name_is_allowed():
    # Static resolution succeeds and the name is harmless, so this must not be
    # over-blocked: legitimate code nodes do read attributes by literal name.
    source = 'def handler(input=""):\n    return {"a": getattr(input, "strip", None)}\n'

    assert _check_python_sandbox(source) == []


def test_namespace_introspection_builtins_are_rejected():
    for builtin in ("vars", "globals", "locals"):
        source = f'def handler(input=""):\n    return {builtin}()\n'

        reasons = _check_python_sandbox(source)

        assert any(builtin in reason for reason in reasons), (builtin, reasons)


def test_setattr_and_delattr_with_computed_name_are_rejected():
    for builtin in ("setattr", "delattr"):
        source = (
            'def handler(input=""):\n'
            f'    {builtin}(object, "__cl" + "ass__", 1)\n'
            "    return {}\n"
        )

        reasons = _check_python_sandbox(source)

        assert any(builtin in reason for reason in reasons), (builtin, reasons)


def test_bare_dynamic_access_reference_is_rejected():
    # Aliasing or passing the builtin as a value defers the attribute name to
    # runtime, so no call site is available to inspect.
    aliased = 'def handler(input=""):\n    g = getattr\n    return {"a": g(object, "__class__")}\n'
    passed = 'def handler(input=""):\n    return list(map(getattr, [object], ["__class__"]))\n'

    assert any("getattr" in r for r in _check_python_sandbox(aliased))
    assert any("getattr" in r for r in _check_python_sandbox(passed))


def test_locally_bound_dynamic_access_name_is_not_flagged():
    # Consistent with builtin shadowing: a local binding means this is the
    # author's own variable, not the builtin.
    source = (
        'def handler(input=""):\n'
        "    getattr = 1\n"
        '    return {"a": getattr}\n'
    )

    assert _check_python_sandbox(source) == []


# ---------------------------------------------------------------------------
# H-3: trust-boundary delimiters for untrusted content in prompts.
# ---------------------------------------------------------------------------


def test_prompt_untrusted_ref_without_delimiter_rejected():
    ir = _ecommerce_faq()
    nodes = list(ir.nodes)
    nodes[2] = nodes[2].model_copy(update={"prompt": "Query: ${input.query}"})  # rerank, no delimiter
    ir = ir.model_copy(update={"nodes": nodes})
    failures = check_policy(ir)
    assert any(
        "untrusted producer 'input'" in f.detail and "delimiter" in f.detail for f in failures
    ), failures


def test_prompt_untrusted_ref_with_delimiter_passes():
    ir = _ecommerce_faq()
    nodes = list(ir.nodes)
    nodes[2] = nodes[2].model_copy(update={"prompt": "Query: <untrusted>${input.query}</untrusted>"})
    ir = ir.model_copy(update={"nodes": nodes})
    failures = check_policy(ir)
    assert not any("delimiter" in f.detail for f in failures), failures
