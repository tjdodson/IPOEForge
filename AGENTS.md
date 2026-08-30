# AGENTS.md — IPOEForge Multi-Session Context

## Project Overview

IPOEForge is a Python CLI tool that builds IPOE (Intelligence Preparation of the Operational Environment) map packages. It downloads basemap tiles, satellite imagery, DEM elevation data, and computes terrain analysis layers for QGIS.

## Current State (as of 2026-08-30)

**Phase 1 complete.** The tool produces 6 raster layers + QML styles for any MGRS-defined area. Published to GitHub at `tjdodson/IPOEForge` with an OpenCode skill for agent-driven usage.

### What Works
- `ipoe build --bbox NW SE --name NAME --mode public --hillshade`
- Downloads OpenTopoMap + ESRI satellite imagery tiles
- Downloads SRTM DEM from AWS, computes slope/hillshade/movement classification
- Outputs individual GeoTIFFs + QML styles in `outputs/{name}/`
- Persistent tile cache at `~/.cache/ipoe/tiles/`
- Batch downloading with retry/backoff for large areas
- 32 unit tests passing

### What Doesn't Exist Yet
- OSM vector layers (roads, hydro, buildings, infrastructure) — Phase 2
- Military symbology via `military-symbol` — Phase 2
- Vegetation density analysis — Phase 3
- Movement vectorization with hatch patterns — Phase 3
- Composite baking — Phase 4

## Key Architecture Decisions

1. **Individual GeoTIFFs, not GPKG** — GPKG raster merging was unreliable. Each layer is its own `.tif` file.
2. **Direct SRTM from AWS** — The `elevation` Python library had issues. We download HGT tiles from `elevation-tiles-prod/skadi/` directly.
3. **MGRS grid via QGIS** — Not a generated layer. Users enable it in QGIS Project > Properties > Grids.
4. **Public-only skill** — The OpenCode skill exclusively uses `--mode public`. No PKI/NGA patterns exposed.
5. **Error strategy** — Warn + skip failed layers, continue building. Don't abort on individual layer failures.

## File Layout

```
IPOEForge/
├── ipoe_forge/
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Data sources (PUBLIC_SOURCES, NGA_SOURCES)
│   ├── models.py            # Bbox, TileCoord, TileGrid, AOIMetadata
│   ├── auth.py              # PKI detection, source resolution
│   ├── tile_downloader.py   # Async XYZ tile fetch + mosaic
│   ├── elevation.py         # SRTM download, slope, hillshade, movement
│   ├── geopackager.py       # GPKG assembly (legacy)
│   └── styles.py            # QML style generation
├── skills/ipoe-forge/SKILL.md  # OpenCode skill
├── tests/                   # 32 unit tests
├── SPEC.md                  # Full specification (v3.0)
├── README.md
├── CONTRIBUTING.md
└── pyproject.toml
```

## Working on This Project

- Run `uv run ruff check && uv run pytest tests/ -v -m "not integration"` before committing
- Follow existing code patterns — don't introduce new frameworks without checking what's already used
- The `--layers` flag is accepted but not wired — don't add new flags unless also wiring them
- All rasters output in EPSG:4326 (WGS84)
- For large area builds, users may need lower zoom (9-11) and larger batch sizes
- The `geopackager.py` module is legacy — the main pipeline uses individual GeoTIFFs

## Phase 2 Plan (Next)

The next agent working on this should:
1. Create `ipoe_forge/osm_features.py` — Overpass API query + GeoDataFrame parsing
2. Wire roads, trails, hydro, buildings, infrastructure into the CLI
3. Add `military-symbol` integration for installation symbols
4. Add QML styles for each new vector layer
5. Update tests and SPEC.md

The Overpass query template is in SPEC.md §7. All OSM tag mappings are in SPEC.md §5.
