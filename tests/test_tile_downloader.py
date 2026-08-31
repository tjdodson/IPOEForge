"""Tests for tile downloading and mosaic."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ipoe_forge.config import TileSource
from ipoe_forge.models import Bbox, TileCoord, TileGrid
from ipoe_forge.tile_downloader import _build_tile_url, _fetch_tile, mosaic_tiles


def test_build_tile_url_standard():
    src = TileSource(name="test", url_template="https://example.com/{z}/{x}/{y}.png")
    coord = TileCoord(z=13, x=4000, y=3000)
    assert _build_tile_url(src, coord) == "https://example.com/13/4000/3000.png"


def test_build_tile_url_arcgis():
    src = TileSource(name="test", url_template="https://example.com/{z}/{y}/{x}", is_arcgis=True)
    coord = TileCoord(z=13, x=4000, y=3000)
    assert _build_tile_url(src, coord) == "https://example.com/13/3000/4000"


def test_tile_grid_from_bbox():
    b = Bbox(west=-77.01, south=38.89, east=-76.99, north=38.91)
    grid = TileGrid.from_bbox(b, zoom=13)
    assert len(grid.tiles) > 0
    assert grid.zoom == 13


def test_mosaic_empty_raises():
    import pytest
    b = Bbox(west=-77.0, south=38.8, east=-76.9, north=38.9)
    with pytest.raises(ValueError, match="No tiles"):
        mosaic_tiles([], b, Path("/tmp/test.tif"), zoom=13)


def test_fetch_tile_logs_warning_on_failure(tmp_path, caplog):
    """_fetch_tile should log at WARNING level when all retries fail."""
    import httpx

    async def run():
        semaphore = asyncio.Semaphore(1)
        cache_path = tmp_path / "tile.png"
        coord = TileCoord(z=13, x=4000, y=3000)

        # Mock client that always raises ConnectError
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("DNS failure")

        with caplog.at_level(logging.WARNING):
            result = await _fetch_tile(
                mock_client, "https://example.com/13/4000/3000.png",
                coord, cache_path, semaphore, retries=2,
            )

        assert result is None
        assert "Failed to fetch tile" in caplog.text
        assert "after 2 attempts" in caplog.text

    asyncio.run(run())


def test_fetch_tile_returns_path_on_success(tmp_path):
    """_fetch_tile should return cache_path on successful download."""
    import httpx

    async def run():
        semaphore = asyncio.Semaphore(1)
        cache_path = tmp_path / "tile.png"
        coord = TileCoord(z=13, x=4000, y=3000)

        # Mock client that returns 200
        mock_response = httpx.Response(200, content=b"fake_png_data")
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await _fetch_tile(
            mock_client, "https://example.com/13/4000/3000.png",
            coord, cache_path, semaphore, retries=3,
        )

        assert result == cache_path
        assert cache_path.exists()
        assert cache_path.read_bytes() == b"fake_png_data"

    asyncio.run(run())


def test_download_tiles_progress_reports_actual_count(tmp_path):
    """Progress callback should report actual downloaded count, not batch count."""
    from ipoe_forge.tile_downloader import download_tiles

    async def run():
        b = Bbox(west=-77.01, south=38.89, east=-76.99, north=38.91)
        src = TileSource(name="test", url_template="https://example.com/{z}/{x}/{y}.png")
        progress_calls = []

        def on_progress(done, total):
            progress_calls.append((done, total))

        # Patch _fetch_tile to always fail
        with patch("ipoe_forge.tile_downloader._fetch_tile", return_value=None):
            result = await download_tiles(
                src, b, 13, tmp_path / "out",
                concurrency=2, batch_size=5, batch_delay=0,
                on_batch_complete=on_progress,
            )

        assert result == []  # No tiles downloaded
        # Progress should show 0 downloaded, not batch count
        assert any(done == 0 for done, _ in progress_calls)

    asyncio.run(run())
