"""SRTM DEM download, slope, hillshade, and movement classification."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from .models import Bbox

logger = logging.getLogger(__name__)


def download_dem(
    bbox: Bbox,
    output_path: Path,
    product: str = "SRTM1",
    margin: float = 0.01,
) -> Path:
    """Download SRTM DEM clipped to a bounding box."""
    import elevation

    padded = bbox.pad(margin)
    bounds = padded.to_tuple()

    logger.info(f"Downloading {product} DEM for {bounds}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    elevation.clip(
        bounds=bounds,
        output=str(output_path),
        product=product,
    )

    logger.info(f"DEM saved to {output_path}")
    return output_path


def compute_slope(dem_path: Path, output_path: Path) -> Path:
    """Compute slope in degrees from a DEM raster."""
    with rasterio.open(dem_path) as src:
        elevation_data = src.read(1).astype(np.float64)
        transform = src.transform
        profile = src.profile.copy()

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)

        mid_lat = (src.bounds.top + src.bounds.bottom) / 2
        m_per_deg_lon = 111132.92 * np.cos(np.radians(mid_lat))
        m_per_deg_lat = 111132.92

        cellsize_x_m = cellsize_x * m_per_deg_lon
        cellsize_y_m = cellsize_y * m_per_deg_lat

        gy, gx = np.gradient(elevation_data, cellsize_y_m, cellsize_x_m)
        slope_rad = np.arctan(np.sqrt(gx**2 + gy**2))
        slope_deg = np.degrees(slope_rad)

        nodata = profile.get("nodata")
        if nodata is not None:
            slope_deg[elevation_data == nodata] = np.nan

        profile.update(dtype="float32", count=1, nodata=np.nan)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(slope_deg.astype(np.float32), 1)

    logger.info(f"Slope raster saved to {output_path}")
    return output_path


def compute_hillshade(
    dem_path: Path,
    output_path: Path,
    azimuth: float = 315.0,
    altitude: float = 45.0,
) -> Path:
    """Compute hillshade from a DEM raster."""
    with rasterio.open(dem_path) as src:
        elevation_data = src.read(1).astype(np.float64)
        transform = src.transform
        profile = src.profile.copy()

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)

        mid_lat = (src.bounds.top + src.bounds.bottom) / 2
        m_per_deg_lon = 111132.92 * np.cos(np.radians(mid_lat))
        m_per_deg_lat = 111132.92

        cellsize_x_m = cellsize_x * m_per_deg_lon
        cellsize_y_m = cellsize_y * m_per_deg_lat

        gy, gx = np.gradient(elevation_data, cellsize_y_m, cellsize_x_m)

        azimuth_rad = np.radians(azimuth)
        altitude_rad = np.radians(altitude)

        slope_rad = np.arctan(np.sqrt(gx**2 + gy**2))
        aspect = np.arctan2(-gy, gx)

        hillshade = (
            np.cos(altitude_rad) * np.cos(slope_rad)
            + np.sin(altitude_rad) * np.sin(slope_rad) * np.cos(azimuth_rad - aspect)
        )
        hillshade = np.clip(hillshade * 255, 0, 255).astype(np.uint8)

        nodata = profile.get("nodata")
        if nodata is not None:
            hillshade[np.isnan(elevation_data)] = 0

        profile.update(dtype="uint8", count=1, nodata=0)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(hillshade, 1)

    logger.info(f"Hillshade saved to {output_path}")
    return output_path


def classify_movement(slope_path: Path, output_path: Path) -> Path:
    """
    Classify terrain for military movement.
    0 = Unrestricted (< 5°), 1 = Restricted (5-15°), 2 = Highly Restricted (> 15°)
    """
    with rasterio.open(slope_path) as src:
        slope_data = src.read(1).astype(np.float64)
        profile = src.profile.copy()

        classified = np.zeros_like(slope_data, dtype=np.uint8)
        classified[slope_data >= 5.0] = 1
        classified[slope_data >= 15.0] = 2

        nodata = profile.get("nodata")
        if nodata is not None:
            classified[np.isnan(slope_data)] = 255

        profile.update(dtype="uint8", nodata=255, compress="deflate")
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(classified, 1)

    logger.info(f"Movement classification saved to {output_path}")
    return output_path


def extract_contours(
    dem_path: Path,
    output_path: Path,
    interval: float = 20.0,
) -> Path:
    """Extract contour lines from DEM using GDAL. Skips if gdal_contour not found."""
    import subprocess

    output_path.parent.mkdir(parents=True, exist_ok=True)
    contour_temp = output_path.with_suffix(".shp")

    cmd = [
        "gdal_contour",
        "-a", "elevation",
        "-i", str(interval),
        "-f", "ESRI Shapefile",
        str(dem_path),
        str(contour_temp),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        logger.info(f"Contours saved to {contour_temp}")

        if output_path.suffix == ".gpkg":
            subprocess.run(
                ["ogr2ogr", "-f", "GPKG", str(output_path), str(contour_temp)],
                check=True, capture_output=True,
            )
            for f in contour_temp.parent.glob(contour_temp.stem + ".*"):
                f.unlink()
        return output_path
    except FileNotFoundError:
        logger.warning("gdal_contour not found — skipping contours")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.warning(f"gdal_contour failed: {e.stderr}")
        return output_path
