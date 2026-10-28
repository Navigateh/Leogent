import typer

from leogent import __version__

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


def main() -> None:
    app()
