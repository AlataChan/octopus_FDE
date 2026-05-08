import json
from pathlib import Path

import click

from loom.ir.models import IRDocument
from loom.runtimes import registry as runtime_registry


@click.command(help="Compile IR to chosen runtime DSL via RuntimeAdapter.")
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", type=click.Choice(["hiagent", "dify"]), default="hiagent",
              help="Target runtime; default hiagent (primary).")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def compile_cmd(ir_file: Path, target: str, out_path: Path) -> None:
    ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
    adapter = runtime_registry.get(target)
    dsl = adapter.compile(ir)
    out_path.write_text(adapter.serialize_dsl(dsl))
    click.echo(f"wrote {out_path} ({target})")
