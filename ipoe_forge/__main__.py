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
from .config import PUBLIC_SOURCES
from .models import AuthMode
from .elevation import (
    classify_movement,
    compute_hillshade,
    compute_slope,
    extract_contours,
    download_dem,
)
from .models import Bbox
from .styles import generate_all_styles
from .tile_downloader import download_and_mosaic

console = Console()


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


def _write_qgis_project(
    project_path: Path,
    layers: list[tuple[str, Path, str]],
    crs: str = "EPSG:4326",
) -> None:
    """Write a QGIS project file (.qgs) that loads all layers with styles."""
    project_dir = project_path.parent

    layer_xml = ""
    for i, (name, tif_path, qml_path) in enumerate(layers):
        # Paths relative to the .qgs file
        try:
            rel_tif = tif_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            rel_tif = tif_path
        try:
            rel_qml = qml_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            rel_qml = qml_path

        style_ref = ""
        if qml_path.exists():
            style_ref = f"""
            <maplayer-style>
              <style>./{rel_qml}</style>
              <selected>0</selected>
            </maplayer-style>"""

        layer_xml += f"""
    <projectlayer type="raster" geometry="Raster" geometrytypes="" polylayer="" pointlayer="" extent="0,0,0,0" crs="{crs}" rotations="" scales="" oacfeatures="">
      <layername>{name}</layername>
      <datasource>./{rel_tif}</datasource>
      <provider encoding="utf-8">gdal</provider>
      <stylecategories>
        <maplayerstylecategory draw="1" si="0" color="255,128,0,255" label="{name}">
          <styles/>
          <style>{name}</style>
        </maplayerstylecategory>
      </stylecategories>
      <customproperties/>
      <blendmode>0</blendmode>
      <opacity>1</opacity>
      <singlebandgray grayBand="1" gradient="BlackToWhite"/>{style_ref}
    </projectlayer>"""

    xml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0" projectname="{project_path.stem}">
  <title>{project_path.stem}</title>
  <projectlayers>{layer_xml}
  </projectlayers>
  <layers/>
  <mapcanvas rotation="0" name="mapcanvas">
    <extent xmax="130" ymax="37" xmin="128" ymin="35"/>
    <layers/>
    < CRS>{crs}</CRS>
  </mapcanvas>
</qgis>"""

    project_path.write_text(xml)


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
    raster_layers: list[tuple[str, Path, str]] = []

    def _add_raster(layer_name: str, tif_path: Path) -> None:
        qml_path = out_dir / "styles" / f"{layer_name}.qml"
        raster_layers.append((layer_name, tif_path, qml_path))

    # Elevation pipeline
    if "elevation" not in skip_set:
        try:
            console.print("[cyan]Downloading DEM...[/cyan]")
            dem_path = out_dir / f"{name}_dem.tif"
            download_dem(aoi_bbox, dem_path, product=dem_product)
            _add_raster("dem", dem_path)

            console.print("[cyan]Computing slope...[/cyan]")
            slope_path = out_dir / f"{name}_slope.tif"
            compute_slope(dem_path, slope_path)
            _add_raster("slope", slope_path)

            if hillshade:
                console.print("[cyan]Computing hillshade...[/cyan]")
                hs_path = out_dir / f"{name}_hillshade.tif"
                compute_hillshade(dem_path, hs_path)
                _add_raster("hillshade", hs_path)

            console.print("[cyan]Classifying movement...[/cyan]")
            movement_path = out_dir / f"{name}_movement.tif"
            classify_movement(slope_path, movement_path)
            _add_raster("movement_class", movement_path)

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
            asyncio.run(download_and_mosaic(sources["topo"], aoi_bbox, zoom, topo_path, concurrency))
            _add_raster("basemap", topo_path)
            status["basemap"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Topo download failed: {e}")
            status["basemap"] = f"failed: {e}"

    if "imagery" not in skip_set:
        try:
            console.print("[cyan]Downloading imagery tiles...[/cyan]")
            img_path = out_dir / f"{name}_imagery.tif"
            asyncio.run(download_and_mosaic(sources["imagery"], aoi_bbox, zoom, img_path, concurrency))
            _add_raster("imagery", img_path)
            status["imagery"] = "success"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Imagery download failed: {e}")
            status["imagery"] = f"failed: {e}"

    # Styles
    style_path = out_dir / "styles"
    console.print(f"[cyan]Generating QML styles → {style_path}[/cyan]")
    generate_all_styles(style_path, zoom)

    # QGIS project file
    qgs_path = out_dir / f"{name}.qgs"
    console.print(f"[cyan]Writing QGIS project → {qgs_path}[/cyan]")
    _write_qgis_project(qgs_path, raster_layers)

    console.print(f"[green]Done: {out_dir}[/green]")
    console.print(f"[green]Open {qgs_path.name} in QGIS to view all layers[/green]")

    if any("failed" in v for v in status.values()):
        sys.exit(1)


if __name__ == "__main__":
    cli()
