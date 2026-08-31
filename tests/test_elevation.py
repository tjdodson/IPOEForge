"""Tests for elevation processing."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from ipoe_forge.elevation import (
    classify_movement,
    compute_hillshade,
    compute_slope,
    srtm_tiles_for_bbox,
)


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


def test_srtm_tiles_use_floor_not_truncation():
    """Regression: int() truncates toward zero and picks the wrong tile.

    Camp Robinson, AR. int(-92.35) is -92 -> "W092", the tile immediately EAST
    of the target. AWS serves it with HTTP 200, so the download appears to
    succeed; the clip then produces a raster that is 100% NoData, and slope,
    hillshade and movement classification are all silently empty.
    """
    assert srtm_tiles_for_bbox(-92.36, 34.79, -92.24, 34.87) == {"N34W093"}


def test_srtm_tiles_southern_hemisphere():
    """Same truncation bug applies to southern latitudes."""
    assert srtm_tiles_for_bbox(-71.6, -33.5, -71.4, -33.3) == {"S34W072"}


def test_srtm_tiles_eastern_hemisphere_unchanged():
    """Positive coordinates: int() and floor() agree, so these always worked."""
    assert srtm_tiles_for_bbox(129.3, 35.90, 129.4, 35.95) == {"N35E129"}


def test_srtm_tiles_spanning_multiple_degrees():
    assert srtm_tiles_for_bbox(-93.5, 34.5, -92.5, 35.5) == {
        "N34W094",
        "N34W093",
        "N35W094",
        "N35W093",
    }


def test_srtm_tiles_exact_integer_boundary():
    """A bbox starting exactly on -92.0 belongs to W092, which covers -92..-91."""
    assert srtm_tiles_for_bbox(-92.0, 34.0, -91.9, 34.1) == {"N34W092"}


def test_download_dem_retries_on_transient_failure(tmp_path, caplog):
    """SRTM download should retry on transient DNS/connection failures."""
    import logging
    import subprocess
    from unittest.mock import MagicMock, patch

    import httpx

    from ipoe_forge.elevation import download_dem
    from ipoe_forge.models import Bbox

    bbox = Bbox(west=-94.1, south=36.1, east=-94.0, north=36.2)
    output = tmp_path / "test_dem.tif"

    call_count = 0
    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("DNS failure")
        # Success on 3rd attempt
        response = MagicMock()
        response.status_code = 200
        # Return minimal valid gzip-compressed HGT data
        import gzip
        import struct
        # N36W094 covers -94..-93 lon, 36..37 lat
        # Create minimal HGT: 3x3 grid of int16 values
        hgt_data = struct.pack(">3h", 100, 200, 300) * 3
        response.content = gzip.compress(hgt_data)
        return response

    with (
        patch("httpx.get", side_effect=mock_get),
        caplog.at_level(logging.INFO),
    ):
        # This will fail because the HGT data is too small for gdalbuildvrt,
        # but we can verify the retry happened
        try:
            download_dem(bbox, output, product="SRTM1")
        except (RuntimeError, ValueError, subprocess.CalledProcessError):
            pass  # Expected - mock data is too small for gdalbuildvrt

    # N36W094: 3 calls (2 failures + 1 final failure), N36W095: 1 call (success)
    assert call_count == 4, f"Expected 4 attempts, got {call_count}"
    # Verify retry logging happened for N36W094
    assert "Retry 1/3" in caplog.text
    assert "Retry 2/3" in caplog.text
