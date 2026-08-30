# IPOEForge Skill Design

## Overview

An OpenCode skill that enables AI agents to generate IPOE map packages from natural language requests. The agent understands intent (place names, military installations, terrain features), resolves coordinates, and drives the `ipoe` CLI to produce QGIS-ready map packages.

## Architecture

Single repo. The skill lives at `skills/ipoe-forge/SKILL.md` alongside the CLI it wraps.

```
IPOEForge/
├── skills/ipoe-forge/SKILL.md   ← OpenCode skill (agent instructions)
├── ipoe_forge/                   ← Python CLI package
├── pyproject.toml
├── README.md
├── SPEC.md
└── outputs/                      ← generated map packages
```

## Skill Design Principles

1. **Lightweight** — SKILL.md stays under 300 lines. No bloated context.
2. **Public-only** — Skill exclusively uses `--mode public`. No PKI/NGA patterns exposed.
3. **Agent-first** — Instructions assume the agent has web search, file tools, and bash.
4. **Progressive** — Ships with Phase 1 capabilities (DEM, tiles, hillshade, movement). Phases 2-4 add more instructions later.

## SKILL.md Structure

### Section 1: What This Tool Does (3-4 sentences)
- IPOE map asset builder
- Downloads DEM, basemap tiles, satellite imagery, terrain analysis
- Outputs individual GeoTIFFs + QML styles for QGIS
- MGRS-based bounding boxes

### Section 2: Installation Check & Setup
- Check if `ipoe` CLI is available
- If not: `git clone`, `cd IPOEForge`, `uv sync`
- Verify with `ipoe --version`

### Section 3: How to Resolve Locations
Agent uses web search to find coordinates, then converts to MGRS:
1. Search for "[place name] coordinates latitude longitude"
2. Convert lat/lon to MGRS4-digit precision using `python3 -c "import mgrs; m=mgrs.MGRS(); print(m.toMGRS(lat, lon, MGRSPrecision=4))"`
3. Need two MGRS strings: northwest corner and southeast corner of the desired area
4. Include buffer for nearby features (military installations, mountain ranges)

### Section 4: Build Command Reference
Concise table of `ipoe build` options with sensible defaults:
- `--bbox` (required): two MGRS strings
- `--name` (required): output directory name
- `--zoom`: 13 default (explain scale tradeoffs)
- `--mode`: always `public`
- `--hillshade`: include by default
- `--concurrency`: 8 default, lower for large areas
- `--batch-size` / `--batch-delay`: for state-wide builds

### Section 5: Agent Workflow
Step-by-step:
1. Parse user request → identify location, scope, features
2. Resolve MGRS coordinates (web search + python conversion)
3. Choose zoom level based on area size
4. Run `ipoe build`
5. Report output location and what was generated

### Section 6: Zoom Level Guide
- Zoom 13: city/tactical (default, ~1km grid)
- Zoom 11: regional/brigade
- Zoom 9: state/corps
- Zoom 8: theater

### Section 7: Output Contents
What the user gets:
- `*_basemap.tif` — topographic map
- `*_imagery.tif` — satellite imagery
- `*_dem.tif` — elevation
- `*_slope.tif` — slope in degrees
- `*_hillshade.tif` — shaded relief
- `*_movement.tif` — military movement classification
- `styles/*.qml` — QGIS styles

### Section 8: Tips & Patterns
- Large areas: lower zoom, increase batch-size
- Military installations: search for post/fort name + "bounds" or "installation area"
- Mountainous terrain: hillshade + slope are key
- Multiple AOIs: run separate builds, user can load all in QGIS

## CLI Changes Required

None. The existing CLI already supports everything the skill needs. The skill is purely instructions — no new code.

## Files to Create

1. `skills/ipoe-forge/SKILL.md` — the skill (target: ~250 lines)
2. `README.md` — updated with installation and skill usage instructions

## Files to Modify

None. The CLI is ready.

## Testing

1. Install from scratch: `git clone` → `uv sync` → `ipoe --version`
2. Agent-driven build: load skill, ask "build me a map of Fort Carson", verify output
3. Large area build: verify batching works for state-wide areas
4. Verify all outputs open correctly in QGIS
