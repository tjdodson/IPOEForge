"""Tests for tile downloading and mosaic."""

from pathlib import Path

from ipoe_forge.config import TileSource
from ipoe_forge.models import Bbox, TileCoord, TileGrid
from ipoe_forge.tile_downloader import _build_tile_url, mosaic_tiles


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
