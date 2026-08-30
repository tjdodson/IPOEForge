"""Tests for elevation processing."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from ipoe_forge.elevation import classify_movement, compute_hillshade, compute_slope


def _make_test_dem(path: Path, width: int = 100, height: int = 100) -> Path:
    """Create a synthetic DEM for testing."""
    data = np.random.rand(height, width).astype(np.float32) * 500
    transform = from_bounds(-77.0, 38.8, -76.9, 38.9, width, height)
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": -9999,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


def test_compute_slope(tmp_path):
    dem = _make_test_dem(tmp_path / "dem.tif")
    slope_path = tmp_path / "slope.tif"
    result = compute_slope(dem, slope_path)
    assert result.exists()
    with rasterio.open(result) as src:
        assert src.dtypes[0] == "float32"
        assert src.read(1).shape == (100, 100)


def test_compute_hillshade(tmp_path):
    dem = _make_test_dem(tmp_path / "dem.tif")
    hs_path = tmp_path / "hillshade.tif"
    result = compute_hillshade(dem, hs_path)
    assert result.exists()
    with rasterio.open(result) as src:
        assert src.dtypes[0] == "uint8"
        data = src.read(1)
        assert data.min() >= 0
        assert data.max() <= 255


def test_classify_movement(tmp_path):
    dem = _make_test_dem(tmp_path / "dem.tif")
    slope_path = tmp_path / "slope.tif"
    compute_slope(dem, slope_path)
    class_path = tmp_path / "movement.tif"
    result = classify_movement(slope_path, class_path)
    assert result.exists()
    with rasterio.open(result) as src:
        data = src.read(1)
        unique = set(np.unique(data))
        assert unique.issubset({0, 1, 2, 255})
