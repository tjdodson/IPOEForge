"""Tests for CLI."""

from click.testing import CliRunner

from ipoe_forge.__main__ import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    from ipoe_forge import __version__
    assert __version__ in result.output


def test_build_requires_bbox():
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "--name", "test"])
    assert result.exit_code != 0
