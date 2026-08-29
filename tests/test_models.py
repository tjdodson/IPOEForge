"""Tests for core data models."""

import pytest
from ipoe_forge.models import Bbox, TileCoord, TileGrid, AOIMetadata, AuthMode, LayerSet


class TestBbox:
    def test_valid_bbox(self):
        b = Bbox(west=-77.0, south=38.8, east=-76.9, north=38.9)
        assert b.west == -77.0
        assert b.east == -76.9
        assert b.width_deg == pytest.approx(0.1)
        assert b.height_deg == pytest.approx(0.1)

    def test_invalid_west_east(self):
        with pytest.raises(ValueError, match="west.*must be < east"):
            Bbox(west=-77.0, south=38.8, east=-77.0, north=38.9)

    def test_invalid_south_north(self):
        with pytest.raises(ValueError, match="south.*must be < north"):
            Bbox(west=-77.0, south=38.9, east=-76.9, north=38.9)

    def test_center(self):
        b = Bbox(west=-77.0, south=38.8, east=-76.8, north=39.0)
        assert b.center == pytest.approx((-76.9, 38.9))

    def test_pad(self):
        b = Bbox(west=-77.0, south=38.8, east=-76.9, north=38.9)
        p = b.pad(0.01)
        assert p.west == pytest.approx(-77.01)
        assert p.east == pytest.approx(-76.89)
        assert p.south == pytest.approx(38.79)
        assert p.north == pytest.approx(38.91)

    def test_to_tuple(self):
        b = Bbox(west=-77.0, south=38.8, east=-76.9, north=38.9)
        assert b.to_tuple() == (-77.0, 38.8, -76.9, 38.9)


class TestTileGrid:
    def test_from_bbox_tile_count(self):
        b = Bbox(west=-77.01, south=38.89, east=-76.99, north=38.91)
        grid = TileGrid.from_bbox(b, zoom=13)
        assert len(grid.tiles) > 0
        assert all(t.z == 13 for t in grid.tiles)

    def test_from_bbox_tile_coords_are_integers(self):
        b = Bbox(west=-77.01, south=38.89, east=-76.99, north=38.91)
        grid = TileGrid.from_bbox(b, zoom=13)
        for tile in grid.tiles:
            assert isinstance(tile.x, int)
            assert isinstance(tile.y, int)


class TestAOIMetadata:
    def test_default_output_path(self):
        m = AOIMetadata(name="test_aoi", bbox=Bbox(west=0, south=0, east=0.1, north=0.1))
        assert m.output_path.name == "test_aoi.gpkg"

    def test_custom_output_path(self):
        from pathlib import Path
        m = AOIMetadata(
            name="test_aoi",
            bbox=Bbox(west=0, south=0, east=0.1, north=0.1),
            output=Path("/tmp/custom.gpkg"),
        )
        assert m.output_path == Path("/tmp/custom.gpkg")


class TestEnums:
    def test_layer_set_values(self):
        assert LayerSet.ALL.value == "all"
        assert LayerSet.INFRA.value == "infra"

    def test_auth_mode_values(self):
        assert AuthMode.AUTO.value == "auto"
        assert AuthMode.PKI.value == "pki"
        assert AuthMode.PUBLIC.value == "public"
