---
name: ipoe-forge
description: Build IPOE map packages (basemap, imagery, DEM, terrain analysis) from MGRS coordinates via CLI
version: 0.1.0
author: Trevor Dodson
tags:
  - gis
  - military
  - terrain
  - maps
  - ipoe
  - elevation
  - qgis
agents:
  - opencode
  - claude
  - cursor
---

# IPOE Map Asset Builder

Build IPOE (Intelligence Preparation of the Operational Environment) map packages from natural language requests. Downloads basemap tiles, satellite imagery, DEM elevation data, and computes terrain analysis layers. Outputs GeoTIFFs with QGIS styles ready for offline use.

## Installation Check

```bash
which ipoe 2>/dev/null || echo "NOT_INSTALLED"
```

If not installed:

```bash
git clone https://github.com/tjdodson/IPOEForge.git /tmp/IPOEForge
cd /tmp/IPOEForge && uv sync
export PATH="$PWD/.venv/bin:$PATH"
```

Verify: `ipoe --version`

### Updating

If installed via skills.sh:
```bash
npx skills update tjdodson/IPOEForge
```

If installed via git:
```bash
cd /path/to/IPOEForge && git pull && uv sync
```

## Dependencies

System requirement: GDAL (`brew install gdal` on macOS, `apt install gdal-bin` on Linux).

## Resolving Locations to MGRS Coordinates

The CLI takes two MGRS4-digit strings (1km grid squares): northwest corner and southeast corner of the desired area.

### Step 1: Find coordinates

Use web search or known coordinates for the location. You need latitude/longitude in decimal degrees.

### Step 2: Convert to MGRS

```bash
python3 -c "
import mgrs
m = mgrs.MGRS()
nw = m.toMGRS(NW_LAT, NW_LON, MGRSPrecision=4)
se = m.toMGRS(SE_LAT, SE_LON, MGRSPrecision=4)
print(f'{nw} {se}')
"
```

### Step 3: Add buffer for nearby features

Military installations and terrain features often span multiple grid squares. Expand the bbox to cover the full area. Common patterns:
- **Fort/base + surrounding terrain**: include 5-10km buffer beyond installation bounds
- **City + mountains**: extend toward the mountain range
- **State-wide**: use zoom 9-10, not 13

## Build Command

```bash
ipoe build \
  --bbox NW_MGRS SE_MGRS \
  --name OUTPUT_NAME \
  --mode public \
  --hillshade
```

### Rebuild from Manifest

Share `build.json` with someone and they can recreate the exact build:

```bash
ipoe rebuild path/to/build.json
```

### Key Options

| Option | Default | Notes |
|--------|---------|-------|
| `--bbox` | required | Two MGRS4-digit strings |
| `--name` | required | Becomes the output directory name |
| `--zoom` | 13 | See zoom guide below |
| `--mode` | auto | Always use `public` |
| `--hillshade` | off | Include — adds shaded relief |
| `--concurrency` | 8 | Lower (2-4) for large areas |
| `--batch-size` | 100 | Increase (200-500) for state-wide |
| `--batch-delay` | 2.0 | Seconds between batches |
| `--skip` | "" | Comma-separated: `imagery,topo,contours` |

### Zoom Level Guide

| Zoom | Scale | Coverage | Use Case |
|------|-------|----------|----------|
| 13 | 1:100k | ~20x25km | City, tactical (default) |
| 11 | 1:500k | ~80x100km | Regional, brigade |
| 10 | 1:1M | ~160x200km | Division area |
| 9 | 1:2M | ~320x400km | State-wide, corps |
| 8 | 1:4M | ~640x800km | Theater |

Rule of thumb: if the bbox spans more than 2 degrees, drop to zoom 10-11.

## Output

Everything goes to `outputs/{name}/`:

```
outputs/{name}/
├── {name}_basemap.tif       Topographic map tiles
├── {name}_imagery.tif       Satellite imagery
├── {name}_dem.tif           SRTM elevation (30m)
├── {name}_slope.tif         Slope in degrees
├── {name}_hillshade.tif     Shaded relief
├── {name}_movement.tif      Military movement class (0/1/2)
└── styles/                  QGIS style files
    ├── basemap.qml
    ├── imagery.qml
    ├── dem.qml
    ├── slope.qml
    ├── hillshade.qml
    └── movement_class.qml
```

Drag any `.tif` into QGIS. Apply styles via Layer Properties > Style > Load Style.

## Movement Classification

The movement layer classifies terrain for vehicle mobility per ATP 2-01.3:

| Class | Value | Slope | Label |
|-------|-------|-------|-------|
| 0 | Unrestricted | < 5° | Open terrain |
| 1 | Restricted | 5-15° | Difficult for vehicles |
| 2 | Highly Restricted | > 15° | Impassable for most vehicles |

## Agent Workflow

1. Parse the request — identify location, scope, what terrain features matter
2. Search for coordinates — "[place name] latitude longitude" or "[fort name] installation bounds"
3. Convert to MGRS — use the python snippet above
4. Choose zoom — based on area size (see guide)
5. Build — `ipoe build --bbox ... --name ... --mode public --hillshade`
6. Report — tell the user where outputs are and what to drag into QGIS

## Examples

### City with nearby installation

```bash
ipoe build \
  --bbox 13SDC9130 13SED5195 \
  --name flying_horse_co \
  --mode public --hillshade
```

### State-wide

```bash
ipoe build \
  --bbox 11SPA9577 12RXV9035 \
  --name arizona \
  --mode public --hillshade \
  --zoom 9 --concurrency 4 --batch-size 300
```

### Quick basemap only (skip analysis)

```bash
ipoe build \
  --bbox 52SEF2009 52SEE4082 \
  --name pohang_korea \
  --mode public \
  --skip imagery,contours
```

## Troubleshooting

- **GDAL not found**: `brew install gdal` (macOS) or `apt install gdal-bin` (Linux)
- **Server disconnection**: Lower `--concurrency` to 2-4, increase `--batch-delay`
- **Tile download slow**: Tiles are cached at `~/.cache/ipoe/tiles/`. Re-runs skip already-downloaded tiles.
- **Large area timeout**: Use `--quiet` flag, lower zoom, or split into multiple builds

## Adding MGRS Grid in QGIS

After loading layers, enable QGIS's native grid:
1. Go to `Project > Properties > Grids`
2. Click the `+` to add a grid
3. Set Interval to `1000` (meters) for1km grid
4. Set CRS to the layer's CRS (EPSG:4326 or project CRS)
5. Choose "Frame" or "Interior annotations" for labels

This is fully dynamic — grid adapts to zoom level automatically.
