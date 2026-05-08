import json
import sys
from pathlib import Path

import click

from loom.validator.validate import validate


@click.command(help="Validate IR file against v0.3 schema + scope rules.")
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--scope", required=True)
def validate_cmd(ir_file: Path, scope: str) -> None:
    doc = json.loads(ir_file.read_text())
    failures = validate(doc, scope=scope)
    if not failures:
        click.echo("OK")
        return
    for f in failures:
        click.echo(f"[{f.bucket}] {f.location or '-'}: {f.detail}", err=True)
    sys.exit(2)
