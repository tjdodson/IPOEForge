# IPOEForge

Automated IPOE map asset builder. Downloads basemap tiles, satellite imagery, DEM elevation data, and computes terrain analysis layers for QGIS.

## Quick Start

```bash
git clone https://github.com/USER/IPOEForge.git
cd IPOEForge
uv sync
```

### System Dependency

```bash
brew install gdal   # macOS
apt install gdal-bin  # Linux
```

## Usage

```bash
ipoe build \
  --bbox 13SDC9130 13SED5195 \
  --name flying_horse_co \
  --mode public --hillshade --mgrs
```

Outputs go to `outputs/{name}/` as GeoTIFFs with QGIS style files.

## AI Agent Skill

IPOEForge includes an OpenCode skill that lets AI agents generate maps from natural language:

> "Build me a map of Fort Huachuca and surrounding terrain"

The skill teaches the agent to resolve coordinates and run the CLI. See `skills/ipoe-forge/SKILL.md`.

## Output Layers

| Layer | Description |
|-------|-------------|
| `*_basemap.tif` | Topographic map tiles |
| `*_imagery.tif` | Satellite imagery |
| `*_dem.tif` | SRTM elevation (30m) |
| `*_slope.tif` | Slope in degrees |
| `*_hillshade.tif` | Shaded relief |
| `*_movement.tif` | Military movement classification |

Use QGIS's native grid (`Project > Properties > Grids`) for dynamic MGRS overlay.

## Movement Classification

| Class | Slope | Label |
|-------|-------|-------|
| 0 | < 5° | Unrestricted |
| 1 | 5-15° | Restricted |
| 2 | > 15° | Highly Restricted |

## Testing

```bash
uv run pytest
uv run ruff check
```
