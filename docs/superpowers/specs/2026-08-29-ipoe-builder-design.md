# IPOEForge — Implementation Design

## Summary

Build a Python CLI tool that downloads geospatial map assets (terrain tiles, elevation, imagery, OSM vectors, military installations) for an MGRS-defined bounding box and packages everything into a single GeoPackage for offline IPOE use on Army systems. All symbology conforms to MIL-STD-2525D / APP-6(D) per ATP 2-01.3.

The `--bbox` flag accepts two MGRS coordinates (4-digit precision) defining top-left and bottom-right corners, snapping the AOI to 1km grid intersections.

## Spec Fixes (from review)

1. **CRS bug in `tile_downloader.py`**: Change `"crs": "EPSG:4326"` to `"crs": "EPSG:3857"` — tiles are Web Mercator, not WGS84. Vectors remain EPSG:4326.
2. **`LayerSet` enum**: Add `INFRA = "infra"` to match the CLI `--layers` parameter.
3. **Overpass queries**: Split the single combined query into 6 category queries (aviation, roads, hydro, infrastructure, buildings/places, military) with 1s delays between. Allows partial failure and prevents 429 rate limits.
4. **Composites**: Deferred to Phase 4 (optional). Individual layers in the GPKG are sufficient for core IPOE use.
5. **Contour extraction**: Remove matplotlib fallback. Require GDAL (`gdal_contour`). If GDAL not found, skip contours with a warning.
6. **Testing strategy**: pytest with unit tests per module + integration test on a small bbox (0.001° square). Mock Overpass/tile servers for unit tests.
7. **Error handling**: Warn + skip failed layers. Metadata records which layers succeeded. User gets a partial package rather than nothing.

## Architecture

### Pipeline Flow

```
CLI (click)
  → Parse MGRS bbox → convert to WGS84 Bbox via `mgrs` library
  → auth.resolve_sources(mode)
  → Create output directory + GPKG
  → Elevation pipeline (sequential):
      DEM download → slope computation → movement classification → contour extraction
  → Tile pipeline (parallel topo + imagery):
      download_tiles() → mosaic_tiles() → write to GPKG
  → OSM pipeline (sequential category queries):
      Overpass (6 queries, 1s delay) → parse JSON → classify into GeoDataFrames → write to GPKG
  → Vegetation (if --vegetation):
      imagery band math (red/green) → float32 density raster → write to GPKG
  → Installations (if military tags found):
      military-symbol SVG generation → write to GPKG
  → MGRS grid (if --mgrs):
      mgrs library → grid polygons → write to GPKG
  → Styles:
      Generate QML files per layer → write to styles/
  → Preview:
      Generate Leaflet.js HTML → write to output dir
  → README:
      Layer descriptions, sources, symbology key
```

### Module Responsibilities

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `__main__.py` | CLI entry point, orchestration, MGRS → WGS84 conversion | click, rich, mgrs |
| `config.py` | Data source configs, thresholds | — |
| `models.py` | Bbox (WGS84, internal), TileCoord, AOIMetadata dataclasses | — |
| `auth.py` | PKI detection, source resolution | httpx, config |
| `tile_downloader.py` | XYZ tile fetch + mosaic to GeoTIFF | httpx, rasterio, PIL |
| `elevation.py` | DEM download, slope, contours, movement class | elevation, rasterio, numpy, GDAL |
| `imagery.py` | Imagery download + vegetation band math | tile_downloader, rasterio |
| `osm_features.py` | Overpass queries + parse to GeoDataFrames | httpx, geopandas, shapely |
| `terrain_analysis.py` | Movement class vectorization + hatch patterns | rasterio, geopandas, shapely |
| `urban_analysis.py` | Urban buildup detection from buildings | geopandas, shapely |
| `installations.py` | Military symbol SVG generation | military_symbol |
| `hydrology.py` | Water feature classification | geopandas (subset of osm_features) |
| `vegetation.py` | Spectral density analysis | rasterio, numpy |
| `mgrs_grid.py` | MGRS grid generation | mgrs, shapely, geopandas |
| `geopackager.py` | Assemble layers into GeoPackage | fiona, geopandas, rasterio |
| `styles/` | QML style templates | — |

### GPKG Layer Strategy

Write each layer to the GPKG as it's completed using `fiona` (vector) or `rasterio` (raster). Don't hold layers in memory. The GPKG supports multiple layers natively.

```
gpkg/
├── basemap (raster)          # mosaic tiles
├── imagery (raster)          # mosaic tiles
├── dem (raster)              # SRTM
├── hillshade (raster)        # computed
├── slope (raster)            # computed
├── vegetation (raster)       # if --vegetation
├── movement_class (vector)   # hatch patterns
├── contours (vector)         # contour lines
├── roads (vector)
├── trails (vector)
├── hydro_rivers (vector)
├── hydro_water (vector)
├── hydro_wetlands (vector)
├── hydro_infra (vector)
├── pipelines (vector)
├── power_lines (vector)
├── bridges (vector)
├── tunnels (vector)
├── barriers (vector)
├── comms_towers (vector)
├── buildings (vector)
├── urban_areas (vector)
├── installations (vector)    # SIDC symbols
├── medical (vector)
├── religious (vector)
├── places (vector)
├── admin_boundaries (vector)
├── mgrs (vector)             # if --mgrs
├── graticule (vector)
└── metadata (table)
```

### Error Handling

- Each layer group is wrapped in try/except
- On failure: log warning, skip layer, continue
- Metadata table records: `{layer_name: "success" | "failed: <reason>"}`
- CLI exit code: 0 if all requested layers succeeded, 1 if any failed

### Overpass Query Strategy

Split into 6 queries, executed sequentially with 1s delay:

1. **Aviation**: `aeroway=*`
2. **Roads**: `highway=*`
3. **Hydrology**: `waterway=*`, `natural=water|wetland`, water infrastructure
4. **Infrastructure**: `man_made=*`, `power=*`, `bridge=*`, `tunnel=*`, `barrier=*`
5. **Buildings & Places**: `building=*`, `place=*`, `admin_level=*`, medical, religious, government
6. **Military**: `military=*`, `landuse=military`

Each query has a 120s timeout. If a query fails, log warning and continue with the next.

### Symbology

#### Movement Classification (Hatch Patterns in QML)
- **Unrestricted** (< 5°): Transparent fill, no hatching
- **Restricted** (5–15°): Single diagonal hatch (45°), 1.5px stroke, 30% opacity gray
- **Highly Restricted** (> 15°): Cross-hatch (45° + 135°), 1.5px stroke, 40% opacity dark gray

QML implementation: SVG fill symbols embedded in `<SVG>` element, used as `fill-image` in the renderer.

#### Urban Buildup (Black Cross-Hatch)
- 45° and 135° intersecting black lines
- 1px stroke, 50% opacity
- Applied to aggregated building polygons

#### Military Installation Symbols
- Generated via `military_symbol` Python package
- SVG output stored in `symbols/` directory
- SIDC codes per the SPEC's SIDC table
- Default affiliation: "Unknown" for all installations

### Dependencies (final)

```
# Core
httpx>=0.27
click>=8.1
rich>=13.0
mgrs>=1.2             # MGRS → WGS84 conversion (required for --bbox)

# Raster
rasterio>=1.3
numpy>=1.24
Pillow>=10.0
GDAL (system)           # gdal_contour, ogr2ogr

# Elevation
elevation>=1.1

# Vector
geopandas>=0.14
fiona>=1.9
shapely>=2.0
pyproj>=3.6

# Military Symbology
military-symbol>=1.0

# Optional
mgrs>=1.2               # MGRS grid layer (if --mgrs flag)

# Dev
pytest
ruff
```

Removed from original SPEC: `requests` (replaced by httpx everywhere).

## Implementation Phases

### Phase 1 — Core Infrastructure (current focus)
- Fix existing: CRS bug, LayerSet enum, add `rasterio` import to tile_downloader
- Build: `__main__.py` CLI, `geopackager.py`, hillshade computation
- Basic QML style generation ( templated strings)
- Integration: wire CLI → auth → download → GPKG

### Phase 2 — OSM Vector Layers
- `osm_features.py` with split Overpass queries
- Parse into GeoDataFrames: roads, trails, hydro, buildings, places, admin, medical, religious, military
- Contour extraction (GDAL required)
- Write all vector layers to GPKG

### Phase 3 — Analysis & Symbology
- `vegetation.py` (spectral density)
- `terrain_analysis.py` (movement class vectorization + hatch QML)
- `urban_analysis.py` (buildup detection + cross-hatch QML)
- `installations.py` (military-symbol SVG)
- MGRS grid
- All QML styles complete
- `preview.html` (Leaflet.js)
- README with legend

### Phase 4 — Polish
- Composite layer baking (optional)
- Error retry with exponential backoff
- Tile caching (avoid re-downloading)
- Progress bars (rich)
- Performance optimization for large bboxes

## Testing Strategy

- **Unit tests**: One test file per module. Mock external APIs (Overpass, tile servers, elevation). Test pure functions (Bbox math, classification thresholds, GeoDataFrame parsing).
- **Integration test**: Run full CLI on a tiny MGRS bbox (single 1km grid square). Verify GPKG has expected layers. Verify raster CRS. Verify vector feature counts are >= 0.
- **Fixture bbox**: Two MGRS coordinates defining a single 1km grid square (e.g. `18TWL8034 18TWL8134`).
- **CI command**: `pytest tests/ -v && ruff check ipoe_builder/`
