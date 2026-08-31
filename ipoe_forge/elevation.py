"""SRTM DEM download, slope, hillshade, and movement classification."""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path

import numpy as np
import rasterio

from .models import Bbox

logger = logging.getLogger(__name__)


def srtm_tiles_for_bbox(west: float, south: float, east: float, north: float) -> set[str]:
    """Return the SRTM 1x1-degree tile names covering a bounding box.

    SRTM tiles are named by their SOUTH-WEST corner, so the tile index is
    ``math.floor()``, not ``int()``. ``int()`` truncates toward zero, so for a
    western longitude such as -92.35 it yields -92 ("W092") instead of -93
    ("W093") -- the tile immediately EAST of the target. That tile exists and
    AWS serves it with HTTP 200, so nothing raises; the DEM is then clipped to
    a window the tile does not cover and comes out entirely NoData.
    """
    tiles: set[str] = set()
    for lat in range(math.floor(south), math.floor(north) + 1):
        for lon in range(math.floor(west), math.floor(east) + 1):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tiles.add(f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}")
    return tiles


def download_dem(
    bbox: Bbox,
    output_path: Path,
    product: str = "SRTM1",
    margin: float = 0.01,
) -> Path:
    """Download SRTM DEM clipped to a bounding box.

    Downloads raw SRTM HGT tiles from AWS terrain tiles, merges them
    with gdal_merge, and clips to the bounding box.
    """
    import gzip
    import subprocess
    import tempfile

    import httpx

    padded = bbox.pad(margin)
    west, south, east, north = padded.to_tuple()

    logger.info(f"Downloading {product} DEM for ({west}, {south}, {east}, {north})...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine which 1x1 degree SRTM tiles we need
    tile_names = srtm_tiles_for_bbox(west, south, east, north)

    logger.info(f"Need SRTM tiles: {sorted(tile_names)}")

    with tempfile.TemporaryDirectory(prefix="ipoe_dem_") as tmpdir:
        tmpdir = Path(tmpdir)
        hgt_files = []

        # Download each tile
        for tile in sorted(tile_names):
            lat_str = tile[1:3]
            ns = tile[0]
            gz_name = f"{tile}.hgt.gz"
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}{lat_str}/{gz_name}"
            hgt_path = tmpdir / f"{tile}.hgt"

            logger.info(f"Downloading {tile}...")
            for attempt in range(3):
                try:
                    resp = httpx.get(url, timeout=60, follow_redirects=True)
                    if resp.status_code == 200:
                        gz_path = tmpdir / gz_name
                        gz_path.write_bytes(resp.content)
                        # Decompress
                        with gzip.open(str(gz_path), "rb") as f_in, open(hgt_path, "wb") as f_out:
                            f_out.write(f_in.read())
                        hgt_files.append(hgt_path)
                        break
                    if resp.status_code == 429:
                        time.sleep(2 ** attempt)
                        continue
                    logger.warning(f"Failed to download {tile}: HTTP {resp.status_code}")
                    break
                except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                    if attempt < 2:
                        logger.info(f"Retry {attempt + 1}/3 for {tile}: {e}")
                        time.sleep(1 + attempt)
                    else:
                        logger.warning(f"Failed to download {tile} after 3 attempts: {e}")

        if not hgt_files:
            raise RuntimeError("No SRTM tiles downloaded")

        # Merge tiles with gdal_merge
        vrt_path = tmpdir / "merged.vrt"
        merge_cmd = [
            "gdalbuildvrt", "-q", "-overwrite",
            str(vrt_path),
        ] + [str(f) for f in hgt_files]

        subprocess.run(merge_cmd, check=True, capture_output=True, timeout=60)

        # Clip to bbox
        clip_cmd = [
            "gdal_translate", "-q",
            "-projwin", str(west), str(north), str(east), str(south),
            "-of", "GTiff",
            "-co", "COMPRESS=DEFLATE",
            str(vrt_path),
            str(output_path),
        ]
        subprocess.run(clip_cmd, check=True, capture_output=True, timeout=60)

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


def classify_movement(
    slope_path: Path,
    output_path: Path,
    unrestricted_max: float = 16.7,
    restricted_max: float = 24.2,
) -> Path:
    """
    Classify terrain for military movement (ATP 2-01.3 Table B-2).
    0 = Unrestricted (< unrestricted_max °)
    1 = Restricted (unrestricted_max – restricted_max °)
    2 = Severely Restricted (> restricted_max °)
    """
    with rasterio.open(slope_path) as src:
        slope_data = src.read(1).astype(np.float64)
        profile = src.profile.copy()

        classified = np.zeros_like(slope_data, dtype=np.uint8)
        classified[slope_data >= unrestricted_max] = 1
        classified[slope_data >= restricted_max] = 2

        nodata = profile.get("nodata")
        if nodata is not None:
            classified[np.isnan(slope_data)] = 255

        profile.update(dtype="uint8", nodata=255, compress="deflate")
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(classified, 1)

    logger.info(f"Movement classification saved to {output_path}")
    return output_path


def vectorize_movement(
    movement_path: Path,
    output_path: Path,
    smooth_radius: int = 10,
    simplify_tolerance: float = 0.0005,
) -> Path:
    """Convert movement classification raster to vector polygons.

    Applies morphological closing to fill gaps and produce cohesive blobs,
    then opening to remove isolated pixels. Only restricted (1) and
    severely restricted (2) are output — unrestricted is implied by absence.

    smooth_radius: morphological structuring element radius in pixels.
    simplify_tolerance: polygon simplification tolerance in CRS units.
    """
    import geopandas as gpd
    from rasterio.features import shapes
    from scipy.ndimage import binary_closing, binary_opening
    from shapely.geometry import shape
    from shapely.ops import unary_union

    logger.info("Vectorizing movement classification...")

    with rasterio.open(movement_path) as src:
        data = src.read(1)
        transform = src.transform

        # Morphological smoothing — closing fills gaps, opening removes speckle
        struct = np.ones((smooth_radius * 2 + 1, smooth_radius * 2 + 1))

        classes = {}
        for value in [1, 2]:
            mask = data == value
            if not mask.any():
                continue
            # Aggressive closing to merge nearby patches into cohesive areas
            mask = binary_closing(mask, structure=struct, iterations=6)
            # Opening to remove isolated pixels
            mask = binary_opening(mask, structure=struct, iterations=3)
            if not mask.any():
                continue

            polys = []
            for geom, val in shapes(data.astype(np.int16), mask=mask, transform=transform):
                if val == value:
                    polys.append(shape(geom))
            if polys:
                merged = unary_union(polys)
                if simplify_tolerance > 0:
                    merged = merged.simplify(simplify_tolerance, preserve_topology=True)
                classes[value] = merged

    # Build GeoDataFrame — only restricted classes
    records = []
    labels = {1: "Restricted", 2: "Severely Restricted"}
    for value, geom in classes.items():
        records.append({"class": value, "label": labels[value], "geometry": geom})

    if not records:
        logger.warning("No restricted polygons found — area may be too flat")
        # Write empty GPKG with correct schema
        import geopandas as gpd
        empty = gpd.GeoDataFrame(
            columns=["class", "label", "geometry"], crs=src.crs
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        empty.to_file(output_path, driver="GPKG", index=False)
        return output_path

    gdf = gpd.GeoDataFrame(records, crs=src.crs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GPKG", index=False)

    logger.info(f"Movement vectors saved to {output_path} ({len(records)} classes)")
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
