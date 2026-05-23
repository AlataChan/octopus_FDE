import click

from loom.cli.commands import brief as cmd_brief
from loom.cli.commands import compile as cmd_compile
from loom.cli.commands import hiagent_push as cmd_hiagent
from loom.cli.commands import plan as cmd_plan
from loom.cli.commands import session as cmd_session
from loom.cli.commands import validate as cmd_validate
from loom.runtimes.bootstrap import register_all


@click.group(help="FDE: deterministic AI workflows.")
def cli() -> None:
    register_all()


cli.add_command(cmd_plan.plan)
cli.add_command(cmd_brief.brief, name="brief")
cli.add_command(cmd_validate.validate_cmd, name="validate")
cli.add_command(cmd_compile.compile_cmd, name="compile")
cli.add_command(cmd_hiagent.hiagent, name="hiagent")
cli.add_command(cmd_session.session, name="session")


if __name__ == "__main__":
    cli()
