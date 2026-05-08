import json
from pathlib import Path

from click.testing import CliRunner

from loom.cli.commands.hiagent_push import _normalize_sys_refs
from loom.cli.main import cli

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_START_NODE_CONFIG = {
    "StartNode": {
        "InputSchema": [
            {"Name": "query", "Type": 0},
            {"Name": "files", "Type": 11},
            {"Name": "chat_histories", "Type": 9},
        ],
        "OutputSchema": [
            {"Name": "query", "Type": 0},
            {"Name": "files", "Type": 11},
            {"Name": "chat_histories", "Type": 9},
        ],
    }
}


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.workspace_id = "ws_1"

    def check_app_by_name(self, name: str) -> bool:
        self.calls.append(("check", name))
        return False

    def create_app(self, *, name: str, app_type: str, description: str, icon: str = "") -> str:
        self.calls.append(("create", (name, app_type, description, icon)))
        return "app_123"

    def save_app_config_draft(self, app_id: str, config_draft: dict) -> None:
        self.calls.append(("save", (app_id, config_draft)))

    def save_chatflow_config_draft(self, app_id: str, chatflow_config: dict) -> None:
        self.calls.append(("save_chatflow", (app_id, chatflow_config)))

    def get_chatflow(self, app_id: str, *, with_node: bool = True) -> dict:
        self.calls.append(("get_chatflow", (app_id, with_node)))
        return {
            "Nodes": [
                {
                    "Code": "server_start",
                    "FlowID": "flow_123",
                    "Type": "Start",
                    "Name": "Start",
                    "Layout": {"X": 100, "Y": 100},
                    "NodeConfig": DEFAULT_START_NODE_CONFIG,
                },
                {
                    "Code": "server_end",
                    "FlowID": "flow_123",
                    "Type": "End",
                    "Name": "End",
                    "Layout": {"X": 1200, "Y": 200},
                    "NodeConfig": {"EndNode": {}},
                },
            ]
        }

    def create_chatflow_node(
        self,
        app_id: str,
        *,
        node_type: str,
        layout: dict,
        name: str = "",
    ) -> dict:
        self.calls.append(("create_node", (app_id, node_type, layout, name)))
        return {
            "Code": f"server_{node_type}_{len(self.calls)}",
            "FlowID": "flow_123",
            "Type": node_type,
            "Name": name,
            "Layout": layout,
            "NodeConfig": {f"{node_type}Node": {}},
        }

    def save_chatflow(self, app_id: str, *, nodes: list[dict], links: list[dict]) -> None:
        self.calls.append(("save_chatflow_graph", (app_id, nodes, links)))

    def publish_app_v2(
        self,
        app_id: str,
        *,
        app_config: dict | None = None,
        chatflow_config: dict | None = None,
        agent_mode: str = "Single",
        version: str,
    ) -> str:
        self.calls.append(("publish", (app_id, app_config, chatflow_config, agent_mode, version)))
        return "pub_123"

    def resolve_default_text_generation_model_id(self) -> str | None:
        self.calls.append(("resolve_model", None))
        return "model_default"

    def resolve_default_dataset_id(self) -> str | None:
        self.calls.append(("resolve_dataset", None))
        return "dataset_default"

    def app_url(self, app_id: str) -> str:
        return f"http://example.test/workspace/ws_1/agent/{app_id}"


def _binding(tmp_path: Path) -> Path:
    path = tmp_path / "bind.yaml"
    path.write_text(
        "customer: test\n"
        "target: hiagent\n"
        "target_version: '2.6'\n"
        "workspace_id: ws_1\n"
    )
    return path


def test_hiagent_push_runs_create_save_publish(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo Agent",
            "--description",
            "Demo description",
        ],
    )
    assert result.exit_code == 0, result.output
    assert [c[0] for c in fake.calls] == [
        "check",
        "create",
        "resolve_model",
        "resolve_dataset",
        "save",
        "publish",
    ]
    assert "http://example.test/workspace/ws_1/agent/app_123" in result.output
    assert "Checking app name" in result.output
    assert "Creating app" in result.output
    assert "Saving draft" in result.output
    assert "Publishing" in result.output
    assert "Agent created and published" in result.output


def test_hiagent_push_stops_when_name_exists(tmp_path, monkeypatch):
    fake = _FakeClient()
    fake.check_app_by_name = lambda name: True  # type: ignore[method-assign]
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo Agent",
        ],
    )
    assert result.exit_code == 2
    assert "already exists" in result.output


def test_hiagent_push_saves_single_agent_config_shape(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo Agent",
        ],
    )
    assert result.exit_code == 0, result.output
    _, (_, draft) = fake.calls[4]
    # The draft is JSON-serializable and uses API AppConfigDraftRequest fields,
    # not the ZIP/YAML-only AppConfig wrapper.
    json.dumps(draft)
    assert "PrePrompt" in draft
    assert "AppID" not in draft


def test_hiagent_push_auto_fills_unbound_model_from_workspace(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo Agent",
        ],
    )
    assert result.exit_code == 0, result.output
    _, (_, draft) = fake.calls[4]
    _, (_, publish_config, _, _, _) = fake.calls[5]
    assert draft["ModelID"] == "model_default"
    assert publish_config["ModelID"] == "model_default"


def test_hiagent_push_defaults_name_from_ir_metadata(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
        ],
    )
    assert result.exit_code == 0, result.output
    assert fake.calls[0] == ("check", "Ecommerce Customer FAQ")
    assert fake.calls[1][0] == "create"
    _, create_args = fake.calls[1]
    assert create_args[0] == "Ecommerce Customer FAQ"
    assert "Name:       Ecommerce Customer FAQ" in result.output


def test_hiagent_push_auto_open_opens_url(tmp_path, monkeypatch):
    fake = _FakeClient()
    opened: list[str] = []
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    monkeypatch.setattr(
        "loom.cli.commands.hiagent_push.webbrowser.open",
        lambda url: opened.append(url) or True,
    )
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo Agent",
            "--auto-open",
        ],
    )
    assert result.exit_code == 0, result.output
    assert opened == ["http://example.test/workspace/ws_1/agent/app_123"]


def test_hiagent_push_mode_chatflow_calls_correct_actions(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("loom.cli.commands.hiagent_push.HiagentAPIClient.from_env", lambda: fake)
    ir_file = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "hiagent",
            "push",
            str(ir_file),
            "--binding",
            str(_binding(tmp_path)),
            "--name",
            "Demo ChatFlow",
            "--mode",
            "chatflow",
        ],
    )
    assert result.exit_code == 0, result.output
    call_names = [c[0] for c in fake.calls]
    assert call_names[:5] == [
        "check",
        "create",
        "resolve_model",
        "resolve_dataset",
        "get_chatflow",
    ]
    assert "create_node" in call_names
    assert call_names[-3:] == ["save_chatflow_graph", "save_chatflow", "publish"]
    _, create_args = fake.calls[1]
    assert create_args[1] == "ChatFlow"
    graph_save_call = next(c for c in fake.calls if c[0] == "save_chatflow_graph")
    _, (_, nodes, links) = graph_save_call
    assert len(nodes) > 1
    assert len(links) > 0
    assert any(n["Type"] == "Knowledge" for n in nodes)
    start_nodes = [n for n in nodes if n["Type"] == "Start"]
    assert len(start_nodes) == 1
    assert start_nodes[0]["NodeConfig"] == DEFAULT_START_NODE_CONFIG
    llm_nodes = [n for n in nodes if n["Type"] == "LLM"]
    assert llm_nodes
    assert any(
        field.get("Name") == "raw_output"
        for field in llm_nodes[0]["NodeConfig"]["LLMNode"]["OutputSchema"]
    )
    config_save_call = next(c for c in fake.calls if c[0] == "save_chatflow")
    _, (_, chatflow_config) = config_save_call
    assert chatflow_config["MetaType"] == "Workflow"
    assert len(chatflow_config["Nodes"]) > 1
    assert chatflow_config["WorkflowID"] == "flow_123"
    publish_call = next(c for c in fake.calls if c[0] == "publish")
    _, (_, app_config, publish_chatflow_config, agent_mode, _) = publish_call
    assert app_config is None
    assert publish_chatflow_config == chatflow_config
    assert agent_mode == ""
    assert "Saving chatflow config draft" in result.output


def test_chatflow_input_refs_normalize_to_server_start_defaults():
    nodes = [
        {"Type": "Start", "Code": "server_start", "NodeConfig": DEFAULT_START_NODE_CONFIG},
        {
            "Type": "LLM",
            "Code": "llm",
            "NodeConfig": {
                "LLMNode": {
                    "Input": [
                        {"Name": "user_question", "RefType": "sys", "Path": "user_question"},
                        {"Name": "attachments", "RefType": "sys", "Path": "attachments"},
                        {"Name": "history", "RefType": "sys", "Path": "chat_history"},
                        {"Name": "custom", "RefType": "sys", "Path": "custom_field"},
                    ]
                }
            },
        },
    ]
    _normalize_sys_refs(nodes)
    refs = nodes[1]["NodeConfig"]["LLMNode"]["Input"]
    assert refs == [
        {"Name": "query", "RefType": "node_field", "Path": "query", "NodeCode": "server_start"},
        {"Name": "files", "RefType": "node_field", "Path": "files", "NodeCode": "server_start"},
        {
            "Name": "chat_histories",
            "RefType": "node_field",
            "Path": "chat_histories",
            "NodeCode": "server_start",
        },
        {"Name": "query", "RefType": "node_field", "Path": "query", "NodeCode": "server_start"},
    ]
