"""CLI entry point for IPOEForge."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
import mgrs
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
)
from .geopackager import GeoPackageBuilder
from .models import AuthMode, Bbox
from .styles import generate_all_styles
from .tile_downloader import download_and_mosaic

console = Console()
logger = logging.getLogger("ipoe_forge")


def _mgrs_to_bbox(top_left: str, bottom_right: str) -> Bbox:
    """Convert two MGRS coordinates (4-digit) to a WGS84 Bbox."""
    m = mgrs.MGRS()

    tl = m.toLatLon(top_left)
    br = m.toLatLon(bottom_right)

    # MGRS toLatLon returns (lat, lon)
    west = min(tl[1], br[1])
    east = max(tl[1], br[1])
    south = min(tl[0], br[0])
    north = max(tl[0], br[0])

    return Bbox(west=west, south=south, east=east, north=north)


@click.group()
@click.version_option(version=__version__, prog_name="IPOEForge")
def cli() -> None:
    """IPOEForge — Automated IPOE map asset builder."""


@cli.command()
@click.option("--bbox", required=True, nargs=2, type=str, help="Top-left and bottom-right MGRS coordinates (4-digit)")
@click.option("--name", required=True, help="AOI identifier")
@click.option("--output", type=click.Path(), default=None, help="Output GeoPackage path")
@click.option("--zoom", type=int, default=13, help="Tile zoom level (8-17)")
@click.option("--mode", type=click.Choice(["auto", "pki", "public"]), default="auto", help="Auth mode")
@click.option("--layers", type=click.Choice(["all", "topo", "imagery", "analysis", "hydro", "infra"]), default="all")
@click.option("--dem-product", type=click.Choice(["SRTM1", "SRTM3"]), default="SRTM1")
@click.option("--contour-interval", type=float, default=20.0, help="Contour interval in meters")
@click.option("--concurrency", type=int, default=8, help="Parallel tile downloads")
@click.option("--mgrs/--no-mgrs", default=False, help="Include MGRS grid layer")
@click.option("--vegetation/--no-vegetation", default=False, help="Vegetation density analysis")
@click.option("--hillshade/--no-hillshade", default=False, help="Computed hillshade layer")
@click.option("--style-dir", type=click.Path(), default=None, help="QML style output directory")
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
    mgrs: bool,
    vegetation: bool,
    hillshade: bool,
    style_dir: str | None,
    skip: str,
    quiet: bool,
) -> None:
    """Build an IPOE map package from an MGRS bounding box."""
    # Configure logging
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    # Parse MGRS bbox
    try:
        aoi_bbox = _mgrs_to_bbox(bbox[0], bbox[1])
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Invalid MGRS coordinates: {e}[/red]")
        sys.exit(1)

    console.print(f"[bold]IPOEForge v{__version__}[/bold]")
    console.print(f"  AOI: {name}")
    console.print(f"  Bbox: {aoi_bbox.to_tuple()}")
    console.print(f"  Zoom: {zoom}")
    console.print(f"  Mode: {mode}")

    # Resolve data sources
    auth_mode = AuthMode(mode)
    try:
        sources, auth_msg = resolve_sources(auth_mode)
    except ConnectionError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    console.print(f"  Sources: {auth_msg}")

    # Skip layers
    skip_set = set(skip.split(",")) if skip else set()

    # Output path
    output_path = Path(output) if output else Path(f"outputs/{name}/{name}.gpkg")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build GPKG
    builder = GeoPackageBuilder(output_path)
    status = {}

    # Elevation pipeline
    if "elevation" not in skip_set:
        try:
            console.print("[cyan]Downloading DEM...[/cyan]")
            dem_path = output_path.parent / f"{name}_dem.tif"
            download_dem(aoi_bbox, dem_path, product=dem_product)

            console.print("[cyan]Computing slope...[/cyan]")
            slope_path = output_path.parent / f"{name}_slope.tif"
            compute_slope(dem_path, slope_path)
            builder.add_raster_layer("slope", slope_path)

            if hillshade:
                console.print("[cyan]Computing hillshade...[/cyan]")
                hs_path = output_path.parent / f"{name}_hillshade.tif"
                compute_hillshade(dem_path, hs_path)
                builder.add_raster_layer("hillshade", hs_path)

            console.print("[cyan]Classifying movement...[/cyan]")
            movement_path = output_path.parent / f"{name}_movement.tif"
            classify_movement(slope_path, movement_path)
            builder.add_raster_layer("movement_class", movement_path)

            if "contours" not in skip_set:
                console.print("[cyan]Extracting contours...[/cyan]")
                contour_path = output_path.parent / f"{name}_contours.gpkg"
                extract_contours(dem_path, contour_path, interval=contour_interval)
                if contour_path.exists():
                    import geopandas as gpd
                    gdf = gpd.read_file(contour_path)
                    builder.add_vector_layer("contours", gdf)

            status["elevation"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Elevation pipeline failed: {e}")
            status["elevation"] = f"failed: {e}"

    # Tile pipeline
    if "topo" not in skip_set:
        try:
            console.print("[cyan]Downloading topo tiles...[/cyan]")
            topo_path = output_path.parent / f"{name}_basemap.tif"
            asyncio.run(download_and_mosaic(sources["topo"], aoi_bbox, zoom, topo_path, concurrency))
            builder.add_raster_layer("basemap", topo_path)
            status["basemap"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Topo download failed: {e}")
            status["basemap"] = f"failed: {e}"

    if "imagery" not in skip_set:
        try:
            console.print("[cyan]Downloading imagery tiles...[/cyan]")
            img_path = output_path.parent / f"{name}_imagery.tif"
            asyncio.run(download_and_mosaic(sources["imagery"], aoi_bbox, zoom, img_path, concurrency))
            builder.add_raster_layer("imagery", img_path)
            status["imagery"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Imagery download failed: {e}")
            status["imagery"] = f"failed: {e}"

    # Metadata
    builder.add_metadata({
        "name": name,
        "bbox": str(aoi_bbox.to_tuple()),
        "zoom": str(zoom),
        "mode": mode,
        "layers": layers,
        "dem_product": dem_product,
        "contour_interval": str(contour_interval),
        "version": __version__,
        **{f"status_{k}": v for k, v in status.items()},
    })

    builder.close()

    # Styles
    if style_dir:
        console.print("[cyan]Generating QML styles...[/cyan]")
        generate_all_styles(Path(style_dir), zoom)

    console.print(f"[green]Done: {output_path}[/green]")

    if any("failed" in v for v in status.values()):
        sys.exit(1)


if __name__ == "__main__":
    cli()
