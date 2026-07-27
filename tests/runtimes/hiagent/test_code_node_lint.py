import re
from typing import Any

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.spec_check import HiagentSpecError
from loom.runtimes.hiagent.v2_6.compiler import compile_ir_chatflow


@pytest.fixture
def binding() -> HiagentBinding:
    return HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
    )


def _code_ir(source: str, *, language: str = "python", node_id: str = "code") -> IRDocument:
    node: dict[str, Any] = {
        "id": node_id,
        "type": "code",
        "rationale": "Exercise the HiAgent Code-node contract.",
        "language": language,
        "source": source,
        "output_schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
        },
    }
    return IRDocument.model_validate({
        "ir_version": "0.3",
        "metadata": {
            "name": "Code Lint Test",
            "owner": "tests",
            "rationale": "Exercise HiAgent Code-node compile linting.",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [],
            "datasets": [],
            "credentials": [],
        },
        "policy": {
            "default_timeout_s": 30,
            "default_retry": {"max_attempts": 2},
            "agent_budget": {
                "max_iterations": 5,
                "max_tokens": 8000,
                "max_wall_clock_s": 300,
            },
        },
        "inputs": [{"name": "query", "type": "string", "required": True}],
        "outputs": [{"name": "answer", "type": "string", "required": False}],
        "nodes": [node],
        "edges": [],
    })


def _compile(source: str, binding: HiagentBinding, *, language: str = "python"):
    return compile_ir_chatflow(_code_ir(source, language=language), binding)


def _emitted_code(bundle: Any) -> str:
    agent = next(value for path, value in bundle.files.items() if path.startswith("agent/"))
    node = agent["AppConfig"]["ChatFlowDetail"]["Nodes"][0]
    return node["Configs"]["Code"]["Code"]


def test_compliant_handler_compiles_without_code_node_warnings(binding: HiagentBinding):
    source = """\
def handler(input=""):
    params = input if isinstance(input, dict) else {}
    query = params.get("query", "")
    return {"answer": query}
"""

    _, warnings = _compile(source, binding)

    assert [warning.code for warning in warnings] == []


def test_fallback_wrapper_is_compliant_with_its_own_linter(binding: HiagentBinding):
    bundle, warnings = _compile("return {'answer': 'ok'}", binding)

    assert _emitted_code(bundle) == (
        'def handler(input=""):\n'
        "    params = input if isinstance(input, dict) else {}\n"
        "    return {'answer': 'ok'}"
    )
    assert [warning.code for warning in warnings] == []


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        (
            """\
def handler(input=None):
    params = input if isinstance(input, dict) else {}
    return {"answer": params.get("query", "")}
""",
            "code_node.handler.signature_style",
        ),
        (
            """\
def handler(input=""):
    return {"answer": ""}
""",
            "code_node.handler.unpack_missing",
        ),
        (
            """\
def handler(input=""):
    params = input if isinstance(input, dict) else {}
    return {"answer": params.get("query")}
""",
            "code_node.handler.get_without_default",
        ),
        (
            """\
def handler(input=""):
    params = input if isinstance(input, dict) else {}
    return {"answer": params["query"]}
""",
            "code_node.handler.direct_index",
        ),
        (
            """\
def handler(input=""):
    params = input if isinstance(input, dict) else {}
    return params
""",
            "code_node.handler.return_params",
        ),
        (
            """\
def handler(input=""):
    params = input if isinstance(input, dict) else {}
    alias = params
    return {"answer": str(bool(alias))}
""",
            "code_node.handler.bypass_direct_get",
        ),
    ],
)
def test_warning_findings_do_not_block_compilation(
    binding: HiagentBinding,
    source: str,
    expected_code: str,
):
    _, warnings = _compile(source, binding)

    matching = [warning for warning in warnings if warning.code == expected_code]
    assert len(matching) == 1
    assert matching[0].node_id == "code"
    assert matching[0].field == "source"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('def handler(input=""):\n    return {', "Invalid Python syntax"),
        ("# def handler( is mentioned but not defined\nvalue = 1", "Missing HiAgent entry function"),
        (
            'def handler(input=""):\n    return {}\n'
            'def handler(input=""):\n    return {}\n',
            "exactly one top-level handler",
        ),
        (
            'def handler(query="", card_state=""):\n    return {}\n',
            "silently",
        ),
        ("def handler(input='', *args):\n    return {}\n", "*args"),
        ("def handler(input='', **kwargs):\n    return {}\n", "**kwargs"),
        ("def handler(input='', *, query=''):\n    return {}\n", "keyword-only"),
    ],
)
def test_fatal_findings_raise_hiagent_spec_error(
    binding: HiagentBinding,
    source: str,
    message: str,
):
    with pytest.raises(HiagentSpecError, match=re.escape(message)) as exc_info:
        _compile(source, binding)

    assert "node 'code'" in str(exc_info.value)


def test_zero_parameter_handler_is_fatal(binding: HiagentBinding):
    with pytest.raises(HiagentSpecError) as exc_info:
        _compile("def handler():\n    return {}\n", binding)

    message = str(exc_info.value)
    assert "always passes one merged dict argument" in message
    assert "raises TypeError at runtime" in message
    assert "[code_node.handler.signature]" in message


def test_javascript_code_nodes_skip_python_contract_lint(binding: HiagentBinding):
    _, warnings = _compile(
        "function handler(query, cardState) { return {answer: query}; }",
        binding,
        language="javascript",
    )

    assert [warning.code for warning in warnings] == []
