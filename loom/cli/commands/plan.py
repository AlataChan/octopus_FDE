import json
import sys
from pathlib import Path

import click

from loom.planner.retry import plan as plan_intent
from loom.planner.types import IntentRequest


@click.command(help="Plan: NL intent + scope -> IR JSON.")
@click.argument("intent_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def plan(intent_file: Path, out_path: Path) -> None:
    req = IntentRequest.model_validate_json(intent_file.read_text())
    res = plan_intent(req)
    if not res.ok:
        click.echo("Planner failed after retries:", err=True)
        for f in res.failures:
            click.echo(f"  [{f.bucket}] {f.detail}", err=True)
        sys.exit(2)
    if res.ir is None:
        click.echo("Planner returned ok=True without IR", err=True)
        sys.exit(2)
    out_path.write_text(json.dumps(res.ir.model_dump(by_alias=True), indent=2))
    click.echo(f"OK in {res.attempts} attempts; ${res.cost_usd:.4f}; {res.latency_s:.1f}s")
