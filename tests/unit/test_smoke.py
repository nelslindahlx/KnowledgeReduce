"""Smoke tests verifying package installation and CLI entrypoint."""

from typer.testing import CliRunner

from knowledgereduce import __version__, app


def test_version_exported() -> None:
    assert __version__ == "1.4.0"


def test_cli_version_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "knowledgereduce 1.4.0" in result.stdout
