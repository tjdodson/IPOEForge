"""Integration test — full CLI on a small MGRS bbox."""

import pytest
from click.testing import CliRunner

from ipoe_forge.__main__ import cli


@pytest.mark.integration
def test_full_build(tmp_path):
    """Run the full pipeline on a 1km MGRS grid square."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build",
        "--bbox", "52SEF2009", "52SEF2109",
        "--name", "test_int",
        "--output", str(tmp_path / "test_int"),
        "--zoom", "13",
        "--mode", "public",
        "--no-hillshade",
        "--quiet",
    ])

    print(result.output)
    if result.exception:
        import traceback
        traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    out_dir = tmp_path / "test_int"
    assert out_dir.exists()
    assert any(out_dir.glob("*.tif"))
