"""Compile an IR file to a target runtime's DSL via RuntimeAdapter."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click
import yaml  # type: ignore[import-untyped]

from loom.ir.models import IRDocument
from loom.runtimes import registry as runtime_registry
from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError
from loom.runtimes.hiagent.v2_6.compiler import compile_ir_chatflow


@click.command(help="Compile IR to chosen runtime DSL via RuntimeAdapter.")
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--target",
    type=click.Choice(["hiagent", "dify"]),
    default="hiagent",
    help="Target runtime; default hiagent [primary].",
)
@click.option(
    "--binding",
    "binding_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Customer Binding YAML [required for hiagent; ignored for dify in v1].",
)
@click.option(
    "--mode",
    type=click.Choice(["chat", "chatflow"]),
    default="chat",
    show_default=True,
    help=(
        "Hiagent zip mode. Default now writes an importable zip; "
        "use --inspect for legacy single-agent YAML inspection."
    ),
)
@click.option(
    "--inspect",
    is_flag=True,
    help="Hiagent only: write legacy single-agent inspection YAML instead of zip.",
)
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def compile_cmd(
    ir_file: Path,
    target: str,
    binding_path: Path | None,
    mode: str,
    inspect: bool,
    out_path: Path,
) -> None:
    ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
    adapter = runtime_registry.get(target)

    binding: HiagentBinding | None = None
    if target == "hiagent":
        if inspect and mode != "chat":
            click.echo("--inspect only supports the chat inspection shape; omit --mode.", err=True)
            sys.exit(2)
        if binding_path is None:
            click.echo(
                "Hiagent target requires --binding <customer-binding.yaml> [per ADR 0024]. "
                "See config/customers/example.hiagent.yaml for the template.",
                err=True,
            )
            sys.exit(2)
        try:
            binding = HiagentBinding.load(binding_path)
        except HiagentBindingError as e:
            click.echo(f"Binding load failed: {e}", err=True)
            sys.exit(2)

        if mode == "chatflow":
            dsl, compile_warnings = compile_ir_chatflow(ir, binding)
        else:
            dsl, compile_warnings = cast("Any", adapter).compile(ir, binding=binding)

        if inspect:
            agent_files = dsl.agent_files()
            if not agent_files:
                click.echo("Hiagent compile produced no agent inspection YAML", err=True)
                sys.exit(2)
            _, agent_yaml = agent_files[0]
            out_path.write_text(yaml.safe_dump(agent_yaml, sort_keys=False, allow_unicode=True))
            click.echo(f"wrote {out_path} (hiagent inspection YAML)")
            return

        zip_path = _hiagent_zip_out_path(out_path)
        if zip_path is None:
            click.echo(
                "use `--inspect` for yaml inspection mode, or pass a .zip path",
                err=True,
            )
            sys.exit(2)
        zip_path.write_bytes(dsl.to_zip_bytes())
        for warning in _hiagent_binding_warnings(ir, dsl):
            click.echo(f"warning: {warning}", err=True)
        for warning in compile_warnings:
            click.echo(f"warning[{warning.code}]: {warning.message}", err=True)
        click.echo(f"wrote {zip_path} (hiagent {mode} zip)")
        click.echo("Next: drag this zip into Hiagent's 导入智能体 wizard.")
        return
    if inspect:
        click.echo("--inspect is only supported for hiagent target.", err=True)
        sys.exit(2)
    else:
        dsl, compile_warnings = adapter.compile(ir)

    serialized = adapter.serialize_dsl(dsl)
    if isinstance(serialized, bytes):
        out_path.write_bytes(serialized)
    else:
        out_path.write_text(serialized)
    for warning in compile_warnings:
        click.echo(f"warning[{warning.code}]: {warning.message}", err=True)
    click.echo(f"wrote {out_path} ({target})")


def _hiagent_zip_out_path(out_path: Path) -> Path | None:
    suffix = out_path.suffix.lower()
    if suffix == ".zip":
        return out_path
    if suffix == "":
        return out_path.with_suffix(".zip")
    return None


def _hiagent_binding_warnings(ir: IRDocument, dsl: Any) -> list[str]:
    agent_files = dsl.agent_files()
    if not agent_files:
        return []
    _, agent_yaml = agent_files[0]
    depends = agent_yaml["AppDepends"]
    warnings: list[str] = []
    has_model = any(getattr(node, "model", None) for node in ir.nodes)
    if has_model and not depends["ModelMap"]:
        warnings.append(
            "no model bound; agent will require manual model selection in Hiagent UI after import"
        )
    if ir.registry_ref.datasets and not depends["KnowledgeMap"]:
        warnings.append(
            "no knowledge bound; agent will require manual knowledge selection in Hiagent UI after import"
        )
    return warnings
