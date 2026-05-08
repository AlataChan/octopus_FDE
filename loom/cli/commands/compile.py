"""Compile an IR file to a target runtime's DSL via RuntimeAdapter."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from loom.ir.models import IRDocument
from loom.runtimes import registry as runtime_registry
from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError


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
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def compile_cmd(
    ir_file: Path,
    target: str,
    binding_path: Path | None,
    out_path: Path,
) -> None:
    ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
    adapter = runtime_registry.get(target)

    binding: HiagentBinding | None = None
    if target == "hiagent":
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
        dsl = cast("Any", adapter).compile(ir, binding=binding)
    else:
        dsl = adapter.compile(ir)

    serialized: Any = adapter.serialize_dsl(dsl)
    if isinstance(serialized, bytes):
        out_path.write_bytes(serialized)
    else:
        out_path.write_text(serialized)

    if target == "hiagent" and binding is not None:
        unbound = _unbound_summary(ir, binding)
        if unbound:
            click.echo(
                f"wrote {out_path} ({target}) - note: {len(unbound)} reference(s) "
                f"unbound, customer will wire in Hiagent UI after import: "
                f"{', '.join(unbound)}"
            )
            return
    click.echo(f"wrote {out_path} ({target})")


def _unbound_summary(ir: IRDocument, binding: HiagentBinding) -> list[str]:
    out: list[str] = []
    for ds in ir.registry_ref.datasets:
        if not binding.resolve_dataset(ds):
            out.append(f"dataset[{ds}]")
    seen: set[str] = set()
    for n in ir.nodes:
        model = getattr(n, "model", None)
        if model and model not in seen:
            seen.add(model)
            if not binding.resolve_model(model):
                out.append(f"model[{model}]")
    return out
