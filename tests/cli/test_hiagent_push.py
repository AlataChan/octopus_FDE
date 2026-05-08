import json
from pathlib import Path

from click.testing import CliRunner

from loom.cli.main import cli

ROOT = Path(__file__).resolve().parents[2]


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

    def publish_app_v2(self, app_id: str, *, app_config: dict, version: str) -> str:
        self.calls.append(("publish", (app_id, app_config, version)))
        return "pub_123"

    def resolve_default_text_generation_model_id(self) -> str | None:
        self.calls.append(("resolve_model", None))
        return "model_default"

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
    assert [c[0] for c in fake.calls] == ["check", "create", "resolve_model", "save", "publish"]
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
    _, (_, draft) = fake.calls[3]
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
    _, (_, draft) = fake.calls[3]
    _, (_, publish_config, _) = fake.calls[4]
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
