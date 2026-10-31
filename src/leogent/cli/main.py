import typer

from leogent import __version__
from leogent.cli.run import register as register_run
from leogent.cli.sessions import register as register_sessions

app = typer.Typer(
    name="leogent",
    no_args_is_help=True,
    help="A small agent runtime you can read, run, and reshape.",
)


@app.callback()
def root() -> None:
    """Leogent command group."""


@app.command("version")
def version() -> None:
    """Print the installed Leogent version."""
    typer.echo(__version__)


register_run(app)
register_sessions(app)


def main() -> None:
    app()
