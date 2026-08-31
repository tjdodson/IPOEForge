"""Async XYZ tile downloader with rate limiting, batching, and persistent cache."""

from __future__ import annotations

import asyncio
import logging
import math
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
DEFAULT_BATCH_SIZE = 100
DEFAULT_BATCH_DELAY = 2.0  # seconds between batches
CACHE_DIR = Path.home() / ".cache" / "ipoe" / "tiles"


async def _fetch_tile(
    client: httpx.AsyncClient,
    url: str,
    coord: TileCoord,
    cache_path: Path,
    semaphore: asyncio.Semaphore,
    retries: int = 3,
) -> Path | None:
    """Download a single tile with retries, using persistent cache."""
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    async with semaphore:
        for attempt in range(retries):
            try:
                resp = await client.get(url, timeout=20.0)
                if resp.status_code == 200 and len(resp.content) > 0:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(resp.content)
                    return cache_path
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(1 + attempt)
                else:
                    logger.warning(f"Failed to fetch tile {coord} after {retries} attempts: {e}")
    return None


def _build_tile_url(source: TileSource, coord: TileCoord) -> str:
    """Build the full URL for a tile coordinate."""
    if source.is_arcgis:
        return source.url_template.format(z=coord.z, y=coord.y, x=coord.x)
    return source.url_template.format(z=coord.z, x=coord.x, y=coord.y)


def _tile_cache_path(source_name: str, zoom: int, coord: TileCoord) -> Path:
    """Get the persistent cache path for a tile."""
    return CACHE_DIR / source_name / str(zoom) / f"{coord.z}_{coord.x}_{coord.y}.png"


async def download_tiles(
    source: TileSource,
    bbox: Bbox,
    zoom: int,
    output_dir: Path,
    concurrency: int = DEFAULT_CONCURRENCY,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
    on_batch_complete: callable | None = None,
) -> list[Path]:
    """Download all tiles for a bbox at a given zoom level.

    Uses persistent cache and downloads in batches to avoid server overload.
    on_batch_complete(done, total) is called after each batch completes.
    """
    grid = TileGrid.from_bbox(bbox, zoom)
    total = len(grid.tiles)
    logger.info(f"Downloading {total} tiles from {source.name} at zoom {zoom}")

    # Check how many are already cached
    cached = sum(1 for c in grid.tiles if _tile_cache_path(source.name, zoom, c).exists())
    to_download = total - cached
    logger.info(f"  {cached} cached, {to_download} to download")

    if to_download == 0:
        # All cached — just return paths
        output_dir.mkdir(parents=True, exist_ok=True)
        return [_tile_cache_path(source.name, zoom, c) for c in grid.tiles]

    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    downloaded: list[Path] = []
    batches = [grid.tiles[i:i + batch_size] for i in range(0, total, batch_size)]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "IPOEForge/0.1 (geospatial-analysis)",
            "Accept": "image/png,image/*",
        },
        follow_redirects=True,
    ) as client:
        for batch_idx, batch in enumerate(batches):
            tasks = [
                _fetch_tile(
                    client,
                    _build_tile_url(source, coord),
                    coord,
                    _tile_cache_path(source.name, zoom, coord),
                    semaphore,
                )
                for coord in batch
            ]
            results = await asyncio.gather(*tasks)
            batch_ok = [p for p in results if p is not None]
            downloaded.extend(batch_ok)

            failed = len(batch) - len(batch_ok)
            if failed:
                logger.warning(f"  batch {batch_idx + 1}: {failed}/{len(batch)} tiles failed")

            done = min((batch_idx + 1) * batch_size, total)
            pct = done / total * 100
            logger.info(f"  batch {batch_idx + 1}/{len(batches)}: {done}/{total} ({pct:.0f}%)")
            if on_batch_complete:
                on_batch_complete(len(downloaded), total)

            # Pause between batches to be kind to servers
            if batch_idx < len(batches) - 1:
                await asyncio.sleep(batch_delay)

    logger.info(f"Downloaded {len(downloaded)}/{total} tiles")
    if len(downloaded) < total:
        logger.warning(f"  {total - len(downloaded)} tiles failed to download from {source.name}")
    return downloaded


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
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
    on_batch_complete: callable | None = None,
) -> Path:
    """High-level: download tiles (with cache) and produce a mosaicked GeoTIFF."""
    tile_paths = await download_tiles(
        source, bbox, zoom, output_path.parent, concurrency, batch_size, batch_delay,
        on_batch_complete=on_batch_complete,
    )
    if not tile_paths:
        raise RuntimeError(f"No tiles downloaded from {source.name}")
    return mosaic_tiles(tile_paths, bbox, output_path, zoom)
