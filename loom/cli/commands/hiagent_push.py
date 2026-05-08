"""Hiagent API push command."""
from __future__ import annotations

import json
import os
import sys
import webbrowser
from pathlib import Path

import click

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.api_client import HiagentAPIClient, HiagentAPIError
from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError
from loom.runtimes.hiagent.v2_6.compiler import (
    build_agent_config_draft,
    build_agent_config_request,
)


@click.group(help="Hiagent self-hosted API operations.")
def hiagent() -> None:
    pass


@hiagent.command(help="Push IR as a Hiagent Chat app: CreateApp -> SaveAppConfigDraft -> PublishAppV2.")
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--binding",
    "binding_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("config/customers/bambu.hiagent.yaml"),
    show_default=True,
    help="Customer Binding YAML.",
)
@click.option("--name", help="Hiagent app name. Defaults to IR metadata.name.")
@click.option("--description", default="", help="Hiagent app description.")
@click.option("--version", "version_name", default="v1.0.0", show_default=True)
@click.option("--auto-open", is_flag=True, help="Open the Hiagent agent URL after publish.")
def push(
    ir_file: Path,
    binding_path: Path,
    name: str | None,
    description: str,
    version_name: str,
    auto_open: bool,
) -> None:
    try:
        ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
        agent_name = name or ir.metadata.name
        agent_description = description or ir.metadata.description or ir.metadata.name
        binding = HiagentBinding.load(binding_path)
        client = HiagentAPIClient.from_env()
        click.echo("Checking app name...")
        if client.check_app_by_name(agent_name):
            click.echo(f"Hiagent app already exists: {agent_name}", err=True)
            sys.exit(2)
        click.echo("Creating app...")
        app_id = client.create_app(
            name=agent_name,
            app_type="Chat",
            description=agent_description,
        )
        binding = _binding_with_model_defaults(ir, binding, client)
        draft = build_agent_config_draft(ir, binding)
        publish_config = build_agent_config_request(ir, binding)
        click.echo("Saving draft...")
        client.save_app_config_draft(app_id, draft)
        click.echo("Publishing...")
        publish_id = client.publish_app_v2(app_id, app_config=publish_config, version=version_name)
    except (HiagentAPIError, HiagentBindingError, ValueError) as e:
        click.echo(f"Hiagent push failed: {e}", err=True)
        sys.exit(2)

    url = client.app_url(app_id)
    click.echo("")
    click.echo(click.style("✓ Agent created and published", fg="green"))
    click.echo("")
    click.echo(f"  Name:       {agent_name}")
    click.echo(f"  Workspace:  {client.workspace_id}")
    click.echo(f"  Agent ID:   {app_id}")
    click.echo(f"  Version:    {publish_id}")
    click.echo(f"  URL:        {click.style(url, fg='blue', underline=True)}")
    click.echo("")
    click.echo("Next: open the URL above to chat with your agent in Hiagent UI.")
    if auto_open:
        _open_browser(url)


def _binding_with_model_defaults(
    ir: IRDocument,
    binding: HiagentBinding,
    client: HiagentAPIClient,
) -> HiagentBinding:
    handles = _model_handles(ir)
    missing = [handle for handle in handles if not binding.resolve_model(handle)]
    if not missing:
        return binding

    model_id = client.resolve_default_text_generation_model_id()
    if not model_id:
        raise HiagentAPIError(
            "no text-generation model is granted to the workspace; set HIAGENT_MODEL_ID "
            "or fill model_id_map in the Hiagent binding"
        )
    model_id_map = {**binding.model_id_map}
    for handle in missing:
        model_id_map[handle] = model_id
    return binding.model_copy(update={"model_id_map": model_id_map})


def _model_handles(ir: IRDocument) -> list[str]:
    out: list[str] = []
    for node in ir.nodes:
        model = getattr(node, "model", None)
        if isinstance(model, str) and model and model not in out:
            out.append(model)
    return out


def _open_browser(url: str) -> None:
    """Open a browser without leaking platform launcher diagnostics to CLI output."""
    with open(os.devnull, "w") as devnull:
        old_stdout = os.dup(1)
        old_stderr = os.dup(2)
        try:
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            opened = webbrowser.open(url)
        finally:
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)
    if not opened:
        click.echo("Note: --auto-open requested, but no local browser accepted the URL.", err=True)
