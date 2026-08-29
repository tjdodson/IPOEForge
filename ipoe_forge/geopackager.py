"""Incremental GeoPackage assembly."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)


class GeoPackageBuilder:
    """Build a GeoPackage layer by layer."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._layers_added: list[str] = []

    def add_vector_layer(self, name: str, gdf: gpd.GeoDataFrame) -> None:
        """Write a GeoDataFrame as a vector layer."""
        if gdf.empty:
            logger.warning(f"Skipping empty layer: {name}")
            return

        gdf.to_file(self.output_path, layer=name, driver="GPKG", index=False)
        self._layers_added.append(name)
        logger.info(f"Added vector layer: {name} ({len(gdf)} features)")

    def add_raster_layer(self, name: str, raster_path: Path) -> None:
        """Write a GeoTIFF as a raster layer in the GPKG."""
        import subprocess

        cmd = [
            "gdal_translate",
            "-of", "GPKG",
            str(raster_path),
            str(self.output_path),
            "-co", f"RASTER_TABLE={name}",
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            self._layers_added.append(name)
            logger.info(f"Added raster layer: {name}")
        except FileNotFoundError:
            logger.warning("gdal_translate not found — skipping raster layer")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to add raster layer {name}: {e.stderr}")

    def add_metadata(self, metadata: dict[str, str]) -> None:
        """Write metadata as a key-value table."""
        import geopandas as gpd
        from shapely.geometry import Point

        gdf = gpd.GeoDataFrame(
            list(metadata.items()),
            columns=["key", "value"],
            geometry=[Point(0, 0)] * len(metadata),
            crs="EPSG:4326",
        )
        gdf.to_file(self.output_path, layer="metadata", driver="GPKG", index=False)
        self._layers_added.append("metadata")
        logger.info(f"Added metadata layer ({len(metadata)} entries)")

    def close(self) -> None:
        """Finalize."""
        logger.info(f"GPKG complete: {self.output_path} ({len(self._layers_added)} layers)")

    @property
    def layers(self) -> list[str]:
        return self._layers_added.copy()
