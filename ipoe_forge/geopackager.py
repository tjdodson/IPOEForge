"""Incremental GeoPackage assembly."""

from __future__ import annotations

import logging
import sqlite3
import subprocess
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)


class GeoPackageBuilder:
    """Build a GeoPackage layer by layer.

    Strategy: raster layers are each written to temporary single-layer GPKGs,
    then merged into the final output via sqlite3.  Vector layers and metadata
    are written directly into the final GPKG via geopandas / sqlite3.
    """

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._layers_added: list[str] = []
        self._raster_tmp: list[tuple[str, Path]] = []

    def add_vector_layer(self, name: str, gdf: gpd.GeoDataFrame) -> None:
        """Write a GeoDataFrame as a vector layer."""
        if gdf.empty:
            logger.warning(f"Skipping empty layer: {name}")
            return

        mode = "a" if self.output_path.exists() else "w"
        gdf.to_file(self.output_path, layer=name, driver="GPKG", index=False, mode=mode)
        self._layers_added.append(name)
        logger.info(f"Added vector layer: {name} ({len(gdf)} features)")

    def add_raster_layer(self, name: str, raster_path: Path) -> None:
        """Create a single-layer GPKG for this raster (will be merged later)."""
        tmp_gpkg = self.output_path.parent / f"_raster_{name}.gpkg"
        try:
            cmd = [
                "gdal_translate", "-of", "GPKG",
                str(raster_path), str(tmp_gpkg),
                "-co", f"RASTER_TABLE={name}",
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            self._raster_tmp.append((name, tmp_gpkg))
            self._layers_added.append(name)
            logger.info(f"Created raster GPKG: {name}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to create raster layer {name}: {e}")
            tmp_gpkg.unlink(missing_ok=True)

    def add_metadata(self, metadata: dict[str, str]) -> None:
        """Write metadata as a key-value table."""
        if not self.output_path.exists():
            logger.warning("GPKG does not exist yet — skipping metadata")
            return

        conn = sqlite3.connect(str(self.output_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL
            )
        """)

        for key, value in metadata.items():
            cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (key, value))

        cursor.execute(
            "SELECT COUNT(*) FROM gpkg_contents WHERE table_name = 'metadata'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO gpkg_contents "
                "(table_name, data_type, srs_id, min_x, min_y, max_x, max_y) "
                "VALUES ('metadata', 'features', 4326, -180, -90, 180, 90)"
            )

        conn.commit()
        conn.close()
        self._layers_added.append("metadata")
        logger.info(f"Added metadata layer ({len(metadata)} entries)")

    def close(self) -> None:
        """Merge all raster GPKGs into the main GPKG and finalize."""
        if self._raster_tmp:
            self._merge_rasters()
        logger.info(f"GPKG complete: {self.output_path} ({len(self._layers_added)} layers)")

    def _merge_rasters(self) -> None:
        """Copy raster tables from temp GPKGs into the main GPKG."""
        if not self.output_path.exists() and self._raster_tmp:
            # No main GPKG yet — just rename the first temp file
            _first_name, first_path = self._raster_tmp[0]
            first_path.rename(self.output_path)
            self._raster_tmp = self._raster_tmp[1:]

        # Copy each raster table into the main GPKG
        for name, tmp_path in self._raster_tmp:
            if not tmp_path.exists():
                continue
            try:
                self._copy_raster_table(tmp_path, name)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to merge raster {name}: {e}")
            finally:
                tmp_path.unlink(missing_ok=True)

    def _copy_raster_table(self, src_gpkg: Path, table_name: str) -> None:
        """Copy a raster table from one GPKG to another using sqlite3."""
        src_conn = sqlite3.connect(str(src_gpkg))
        dst_conn = sqlite3.connect(str(self.output_path))

        src_cursor = src_conn.cursor()
        dst_cursor = dst_conn.cursor()

        # Get all tables from source
        src_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'rtree_%' "
            "AND name != 'sqlite_sequence'"
        )
        tables = [row[0] for row in src_cursor.fetchall()]

        for table in tables:
            # Copy table schema
            src_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
            row = src_cursor.fetchone()
            if row:
                dst_cursor.execute(f"DROP TABLE IF EXISTS \"{table}\"")
                dst_cursor.execute(row[0])

            # Copy data
            src_cursor.execute(f"SELECT * FROM \"{table}\"")
            columns = [desc[0] for desc in src_cursor.description]
            rows = src_cursor.fetchall()
            if rows:
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join([f'"{c}"' for c in columns])
                dst_cursor.executemany(
                    f"INSERT INTO \"{table}\" ({col_names}) VALUES ({placeholders})",
                    rows,
                )

        # Copy gpkg_contents entry for this raster
        src_cursor.execute(
            "SELECT * FROM gpkg_contents WHERE table_name = ?", (table_name,)
        )
        content_row = src_cursor.fetchone()
        if content_row:
            src_cursor.execute(
                "PRAGMA table_info(gpkg_contents)"
            )
            col_names = [desc[1] for desc in src_cursor.fetchall()]
            placeholders = ", ".join(["?"] * len(col_names))
            col_str = ", ".join([f'"{c}"' for c in col_names])
            # Only insert if not already present
            dst_cursor.execute(
                "SELECT COUNT(*) FROM gpkg_contents WHERE table_name = ?",
                (table_name,),
            )
            if dst_cursor.fetchone()[0] == 0:
                dst_cursor.execute(
                    f"INSERT INTO gpkg_contents ({col_str}) VALUES ({placeholders})",
                    content_row,
                )

        # Copy gpkg_tile_matrix_set entry
        src_cursor.execute(
            "SELECT * FROM gpkg_tile_matrix_set WHERE table_name = ?", (table_name,)
        )
        tms_row = src_cursor.fetchone()
        if tms_row:
            dst_cursor.execute(
                "SELECT COUNT(*) FROM gpkg_tile_matrix_set WHERE table_name = ?",
                (table_name,),
            )
            if dst_cursor.fetchone()[0] == 0:
                dst_cursor.execute(
                    "INSERT INTO gpkg_tile_matrix_set "
                    "(table_name, srs_id, min_x, min_y, max_x, max_y) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    tms_row,
                )

        # Copy gpkg_tile_matrix entries
        src_cursor.execute(
            "SELECT * FROM gpkg_tile_matrix WHERE table_name = ?", (table_name,)
        )
        for tm_row in src_cursor.fetchall():
            dst_cursor.execute(
                "SELECT COUNT(*) FROM gpkg_tile_matrix "
                "WHERE table_name = ? AND zoom_level = ?",
                (table_name, tm_row[1]),
            )
            if dst_cursor.fetchone()[0] == 0:
                dst_cursor.execute(
                    "INSERT INTO gpkg_tile_matrix "
                    "(table_name, zoom_level, matrix_width, matrix_height, "
                    "tile_width, tile_height, pixel_x_size, pixel_y_size) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    tm_row,
                )

        # Copy raster tile data
        src_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            f"AND name LIKE '{table_name}%' AND name != '{table_name}'"
        )
        tile_tables = [row[0] for row in src_cursor.fetchall()]
        for tile_table in tile_tables:
            src_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tile_table}'")
            row = src_cursor.fetchone()
            if row:
                dst_cursor.execute(f"DROP TABLE IF EXISTS \"{tile_table}\"")
                dst_cursor.execute(row[0])

            src_cursor.execute(f"SELECT * FROM \"{tile_table}\"")
            columns = [desc[0] for desc in src_cursor.description]
            rows = src_cursor.fetchall()
            if rows:
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join([f'"{c}"' for c in columns])
                dst_cursor.executemany(
                    f"INSERT INTO \"{tile_table}\" ({col_names}) VALUES ({placeholders})",
                    rows,
                )

        dst_conn.commit()
        src_conn.close()
        dst_conn.close()
        logger.info(f"Merged raster table: {table_name}")
