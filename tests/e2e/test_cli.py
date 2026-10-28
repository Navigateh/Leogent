from typer.testing import CliRunner

from leogent import __version__
from leogent.cli.main import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
