"""IPOEForge CLI — automated IPOE map asset builder."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from . import __version__
from .auth import resolve_sources
from .elevation import (
    classify_movement,
    compute_hillshade,
    compute_slope,
    download_dem,
    extract_contours,
    vectorize_movement,
)
from .models import AuthMode, Bbox
from .styles import generate_all_styles
from .tile_downloader import download_and_mosaic

console = Console()
logger = logging.getLogger(__name__)


def _mgrs_to_bbox(mgrs_top_left: str, mgrs_bottom_right: str) -> Bbox:
    """Convert two MGRS 4-digit grid squares to a WGS84 bounding box."""
    import mgrs

    tl = mgrs.MGRS()
    coords1 = tl.toLatLon(mgrs_top_left)
    br = mgrs.MGRS()
    coords2 = br.toLatLon(mgrs_bottom_right)

    south = min(coords1[0], coords2[0])
    north = max(coords1[0], coords2[0])
    west = min(coords1[1], coords2[1])
    east = max(coords1[1], coords2[1])

    return Bbox(west=west, south=south, east=east, north=north)


@click.group()
@click.version_option(__version__, prog_name="IPOEForge")
def cli() -> None:
    """IPOEForge — automated IPOE map asset builder."""


@cli.command()
@click.option("--bbox", required=True, nargs=2, type=str, help="Top-left and bottom-right MGRS coordinates (4-digit)")
@click.option("--name", required=True, help="AOI identifier")
@click.option("--output", type=click.Path(), default=None, help="Output directory (default: outputs/{name})")
@click.option("--zoom", type=int, default=13, help="Tile zoom level (8-17)")
@click.option("--mode", type=click.Choice(["auto", "pki", "public"]), default="auto", help="Auth mode")
@click.option("--layers", type=click.Choice(["all", "topo", "imagery", "analysis", "hydro", "infra"]), default="all")
@click.option("--dem-product", type=click.Choice(["SRTM1", "SRTM3"]), default="SRTM1")
@click.option("--contour-interval", type=float, default=20.0, help="Contour interval in meters")
@click.option("--concurrency", type=int, default=8, help="Parallel tile downloads")
@click.option("--batch-size", type=int, default=100, help="Tiles per batch")
@click.option("--batch-delay", type=float, default=2.0, help="Seconds between batches")
@click.option("--hillshade/--no-hillshade", default=False, help="Computed hillshade layer")
@click.option("--skip", type=str, default="", help="Comma-separated layers to skip")
@click.option("--quiet/--no-quiet", default=False, help="Suppress progress")
def build(
    bbox: tuple[str, str],
    name: str,
    output: str | None,
    zoom: int,
    mode: str,
    layers: str,
    dem_product: str,
    contour_interval: float,
    concurrency: int,
    batch_size: int,
    batch_delay: float,
    hillshade: bool,
    skip: str,
    quiet: bool,
) -> None:
    """Build an IPOE map package from an MGRS bounding box."""
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    try:
        aoi_bbox = _mgrs_to_bbox(bbox[0], bbox[1])
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Invalid MGRS coordinates: {e}[/red]")
        sys.exit(1)

    console.print(f"[bold]IPOEForge v{__version__}[/bold]")
    console.print(f"  AOI: {name}")
    console.print(f"  Bbox: {aoi_bbox.to_tuple()}")
    console.print(f"  Zoom: {zoom}")

    # Resolve sources
    auth_mode = AuthMode(mode)
    sources, source_msg = resolve_sources(auth_mode)
    console.print(f"  Mode: {auth_mode.value}")
    console.print(f"  Sources: {source_msg}")

    # Output directory
    out_dir = Path(output) if output else Path(f"outputs/{name}")
    out_dir.mkdir(parents=True, exist_ok=True)

    skip_set = set(skip.split(",")) if skip else set()
    status: dict[str, str] = {}

    # Elevation pipeline
    if "elevation" not in skip_set:
        try:
            console.print("[cyan]Downloading DEM...[/cyan]")
            dem_path = out_dir / f"{name}_dem.tif"
            download_dem(aoi_bbox, dem_path, product=dem_product)

            console.print("[cyan]Computing slope...[/cyan]")
            slope_path = out_dir / f"{name}_slope.tif"
            compute_slope(dem_path, slope_path)

            if hillshade:
                console.print("[cyan]Computing hillshade...[/cyan]")
                hs_path = out_dir / f"{name}_hillshade.tif"
                compute_hillshade(dem_path, hs_path)

            console.print("[cyan]Classifying movement...[/cyan]")
            movement_path = out_dir / f"{name}_movement.tif"
            classify_movement(slope_path, movement_path)

            console.print("[cyan]Vectorizing movement classification...[/cyan]")
            movement_vec_path = out_dir / f"{name}_movement_class.gpkg"
            vectorize_movement(movement_path, movement_vec_path)

            if "contours" not in skip_set:
                console.print("[cyan]Extracting contours...[/cyan]")
                contour_path = out_dir / f"{name}_contours.gpkg"
                extract_contours(dem_path, contour_path, interval=contour_interval)

            status["elevation"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Elevation pipeline failed: {e}")
            status["elevation"] = f"failed: {e}"

    # Tile pipeline
    if "topo" not in skip_set:
        try:
            console.print("[cyan]Downloading topo tiles...[/cyan]")
            topo_path = out_dir / f"{name}_basemap.tif"
            asyncio.run(download_and_mosaic(sources["topo"], aoi_bbox, zoom, topo_path, concurrency, batch_size, batch_delay))
            status["basemap"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Topo download failed: {e}")
            status["basemap"] = f"failed: {e}"

    if "imagery" not in skip_set:
        try:
            console.print("[cyan]Downloading imagery tiles...[/cyan]")
            img_path = out_dir / f"{name}_imagery.tif"
            asyncio.run(download_and_mosaic(sources["imagery"], aoi_bbox, zoom, img_path, concurrency, batch_size, batch_delay))
            status["imagery"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Imagery download failed: {e}")
            status["imagery"] = f"failed: {e}"

    # Styles
    style_path = out_dir / "styles"
    console.print(f"[cyan]Generating QML styles → {style_path}[/cyan]")
    generate_all_styles(style_path, zoom)

    console.print(f"\n[green]Done: {out_dir}[/green]")
    console.print("[green]Drag .tif files into QGIS to view layers[/green]")

    if any("failed" in v for v in status.values()):
        sys.exit(1)


if __name__ == "__main__":
    cli()
