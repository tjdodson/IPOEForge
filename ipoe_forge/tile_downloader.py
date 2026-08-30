"""Async XYZ tile downloader with rate limiting and mosaic output."""

from __future__ import annotations

import asyncio
import logging
import math
import tempfile
from pathlib import Path

import httpx
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds

from .config import TileSource
from .models import Bbox, TileCoord, TileGrid

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 8
TILE_SIZE = 256


async def _fetch_tile(
    client: httpx.AsyncClient,
    url: str,
    coord: TileCoord,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> Path | None:
    """Download a single tile."""
    tile_path = output_dir / f"{coord.z}_{coord.x}_{coord.y}.png"
    if tile_path.exists():
        return tile_path

    async with semaphore:
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 200 and len(resp.content) > 0:
                tile_path.write_bytes(resp.content)
                return tile_path
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.debug(f"Failed to fetch tile {coord}: {e}")
    return None


def _build_tile_url(source: TileSource, coord: TileCoord) -> str:
    """Build the full URL for a tile coordinate."""
    if source.is_arcgis:
        return source.url_template.format(z=coord.z, y=coord.y, x=coord.x)
    return source.url_template.format(z=coord.z, x=coord.x, y=coord.y)


async def download_tiles(
    source: TileSource,
    bbox: Bbox,
    zoom: int,
    output_dir: Path,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[Path]:
    """Download all tiles for a bbox at a given zoom level."""
    grid = TileGrid.from_bbox(bbox, zoom)
    logger.info(f"Downloading {len(grid.tiles)} tiles from {source.name} at zoom {zoom}")

    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "IPOEForge/0.1 (geospatial-analysis)",
            "Accept": "image/png,image/*",
        },
        follow_redirects=True,
    ) as client:
        tasks = [
            _fetch_tile(client, _build_tile_url(source, coord), coord, output_dir, semaphore)
            for coord in grid.tiles
        ]
        results = await asyncio.gather(*tasks)

    tile_paths = [p for p in results if p is not None]
    logger.info(f"Downloaded {len(tile_paths)}/{len(grid.tiles)} tiles")
    return tile_paths


def mosaic_tiles(
    tile_paths: list[Path],
    bbox: Bbox,
    output_path: Path,
    zoom: int,
    tile_size: int = TILE_SIZE,
) -> Path:
    """Stitch downloaded tiles into a single GeoTIFF (EPSG:4326)."""
    if not tile_paths:
        raise ValueError("No tiles to mosaic")

    tile_lookup = {}
    for p in tile_paths:
        parts = p.stem.split("_")
        tile_lookup[(int(parts[0]), int(parts[1]), int(parts[2]))] = p

    grid = TileGrid.from_bbox(bbox, zoom)
    if not grid.tiles:
        raise ValueError("Empty tile grid")

    xs = [t.x for t in grid.tiles]
    ys = [t.y for t in grid.tiles]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    grid_width = (x_max - x_min + 1) * tile_size
    grid_height = (y_max - y_min + 1) * tile_size

    mosaic = Image.new("RGBA", (grid_width, grid_height), (0, 0, 0, 0))

    tiles_placed = 0
    for coord in grid.tiles:
        key = (coord.z, coord.x, coord.y)
        if key in tile_lookup:
            tile_img = Image.open(tile_lookup[key]).convert("RGBA")
            px = (coord.x - x_min) * tile_size
            py = (coord.y - y_min) * tile_size
            mosaic.paste(tile_img, (px, py))
            tiles_placed += 1

    logger.info(f"Mosaic: placed {tiles_placed} tiles into {grid_width}x{grid_height}")

    # Compute WGS84 bounds from tile coordinates
    n = 2**zoom
    west = (x_min / n) * 360.0 - 180.0
    east = ((x_max + 1) / n) * 360.0 - 180.0

    def y_to_lat(y: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))

    north = y_to_lat(y_min)
    south = y_to_lat(y_max + 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    mosaic_array = np.array(mosaic)
    transform = from_bounds(west, south, east, north, grid_width, grid_height)

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": grid_width,
        "height": grid_height,
        "count": 4,
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "deflate",
        "tiled": True,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        for band_idx in range(4):
            dst.write(mosaic_array[:, :, band_idx], band_idx + 1)

    logger.info(f"Mosaic saved to {output_path}")
    return output_path


async def download_and_mosaic(
    source: TileSource,
    bbox: Bbox,
    zoom: int,
    output_path: Path,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> Path:
    """High-level: download tiles and produce a mosaicked GeoTIFF."""
    with tempfile.TemporaryDirectory(prefix="ipoe_tiles_") as tmpdir:
        tile_dir = Path(tmpdir) / "tiles"
        tile_paths = await download_tiles(source, bbox, zoom, tile_dir, concurrency)
        if not tile_paths:
            raise RuntimeError(f"No tiles downloaded from {source.name}")
        return mosaic_tiles(tile_paths, bbox, output_path, zoom)
