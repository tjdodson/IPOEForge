"""Tests for GeoPackage assembly."""

import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point
from ipoe_forge.geopackager import GeoPackageBuilder


def test_create_gpkg(tmp_path):
    gpkg = tmp_path / "test.gpkg"
    builder = GeoPackageBuilder(gpkg)
    gdf = gpd.GeoDataFrame(
        {"name": ["A"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    builder.add_vector_layer("points", gdf)
    builder.add_metadata({"test": "value"})
    builder.close()
    assert gpkg.exists()


def test_add_vector_layer(tmp_path):
    gpkg = tmp_path / "test.gpkg"
    builder = GeoPackageBuilder(gpkg)

    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B"], "geometry": [Point(0, 0), Point(1, 1)]},
        crs="EPSG:4326",
    )
    builder.add_vector_layer("points", gdf)
    builder.close()

    result = gpd.read_file(gpkg, layer="points")
    assert len(result) == 2
    assert result.crs.to_epsg() == 4326


def test_add_metadata(tmp_path):
    gpkg = tmp_path / "test.gpkg"
    builder = GeoPackageBuilder(gpkg)

    gdf = gpd.GeoDataFrame(
        {"name": ["A"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    builder.add_vector_layer("points", gdf)
    builder.add_metadata({"name": "test", "zoom": "13"})
    builder.close()

    import sqlite3
    conn = sqlite3.connect(str(gpkg))
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM metadata ORDER BY key")
    rows = dict(cursor.fetchall())
    conn.close()
    assert rows["name"] == "test"
    assert rows["zoom"] == "13"
