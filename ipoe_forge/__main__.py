"""IPOEForge CLI — automated IPOE map asset builder."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
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


def _build_manifest(
    name: str,
    bbox_input: tuple[str, str],
    aoi_bbox: Bbox,
    zoom: int,
    mode: str,
    dem_product: str,
    contour_interval: float,
    hillshade: bool,
    sources: dict,
    status: dict[str, str],
    out_dir: Path,
) -> dict:
    """Generate a build manifest JSON for reproducibility."""
    # Collect output files with sizes
    outputs = {}
    for f in sorted(out_dir.iterdir()):
        if f.is_file() and f.suffix in (".tif", ".gpkg"):
            outputs[f.name] = {
                "size_bytes": f.stat().st_size,
                "format": f.suffix.lstrip("."),
            }
    # Styles
    style_dir = out_dir / "styles"
    if style_dir.is_dir():
        outputs["styles/"] = {
            "files": [s.name for s in sorted(style_dir.glob("*.qml"))],
            "count": len(list(style_dir.glob("*.qml"))),
        }

    return {
        "ipoe_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aoi": {
            "name": name,
            "mgrs_bbox": list(bbox_input),
            "wgs84_bbox": {
                "west": aoi_bbox.west,
                "south": aoi_bbox.south,
                "east": aoi_bbox.east,
                "north": aoi_bbox.north,
            },
        },
        "parameters": {
            "zoom": zoom,
            "mode": mode,
            "dem_product": dem_product,
            "contour_interval_m": contour_interval,
            "hillshade": hillshade,
        },
    "sources": {
        k: {"name": v.name, "url_template": v.url_template, "attribution": v.attribution}
        for k, v in sources.items()
    },
        "layers": status,
        "outputs": outputs,
    }


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

    # Build manifest
    manifest = _build_manifest(
        name=name, bbox_input=bbox, aoi_bbox=aoi_bbox, zoom=zoom,
        mode=mode, dem_product=dem_product, contour_interval=contour_interval,
        hillshade=hillshade, sources=sources, status=status, out_dir=out_dir,
    )
    manifest_path = out_dir / "build.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    console.print(f"[cyan]Build manifest → {manifest_path}[/cyan]")

    console.print(f"\n[green]Done: {out_dir}[/green]")
    console.print("[green]Drag .tif files into QGIS to view layers[/green]")

    if any("failed" in v for v in status.values()):
        sys.exit(1)


@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True))
@click.option("--output", type=click.Path(), default=None, help="Output directory (default: original location)")
@click.option("--concurrency", type=int, default=8, help="Parallel tile downloads")
@click.option("--batch-size", type=int, default=100, help="Tiles per batch")
@click.option("--batch-delay", type=float, default=2.0, help="Seconds between batches")
@click.option("--skip", type=str, default="", help="Comma-separated layers to skip")
@click.option("--quiet/--no-quiet", default=False, help="Suppress progress")
def rebuild(
    manifest_path: str,
    output: str | None,
    concurrency: int,
    batch_size: int,
    batch_delay: float,
    skip: str,
    quiet: bool,
) -> None:
    """Rebuild a map package from a build.json manifest."""
    import json as json_mod

    manifest = json_mod.loads(Path(manifest_path).read_text())

    name = manifest["aoi"]["name"]
    mgrs_bbox = manifest["aoi"]["mgrs_bbox"]
    params = manifest["parameters"]

    # Reconstruct bbox tuple for the build command
    bbox_tuple = tuple(mgrs_bbox)

    # Build kwargs from manifest
    build_kwargs = {
        "bbox": bbox_tuple,
        "name": name,
        "output": output or str(Path(manifest_path).parent),
        "zoom": params["zoom"],
        "mode": params["mode"],
        "layers": "all",
        "dem_product": params["dem_product"],
        "contour_interval": params["contour_interval_m"],
        "concurrency": concurrency,
        "batch_size": batch_size,
        "batch_delay": batch_delay,
        "hillshade": params["hillshade"],
        "skip": skip,
        "quiet": quiet,
    }

    console.print(f"[bold]Rebuilding from {manifest_path}[/bold]")
    console.print(f"  Original build: {manifest.get('generated_at', 'unknown')}")
    console.print(f"  IPOEForge version: {manifest.get('ipoe_version', 'unknown')}")

    # Delegate to build command
    ctx = click.Context(build)
    ctx.invoke(build, **build_kwargs)


if __name__ == "__main__":
    cli()
