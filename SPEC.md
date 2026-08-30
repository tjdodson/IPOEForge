# IPOEForge — Specification v3.0

## Purpose

Automate the creation of IPOE map packages from a single CLI command. Define an MGRS bounding box, get individual GeoTIFFs with QML styles for every layer needed for terrain analysis, movement planning, and operational visualization — offline-capable for Army systems, with all symbology conforming to **MIL-STD-2525D / APP-6(D)** per **ATP 2-01.3**.

---

## 1. Input Parameters

| Parameter | Type | Required | Default | Status | Description |
|-----------|------|----------|---------|--------|-------------|
| `--bbox` | 2 MGRS strings | Yes | — | ✅ | Top-left and bottom-right MGRS coordinates (4-digit precision) |
| `--name` | string | Yes | — | ✅ | AOI identifier |
| `--output` | path | No | `outputs/{name}` | ✅ | Output directory (diverged from GPKG) |
| `--zoom` | int | No | 13 | ✅ | Tile zoom 8–17 |
| `--mode` | enum | No | `auto` | ✅ | `auto` / `pki` / `public` |
| `--layers` | enum | No | `all` | ⚠️ | `all` / `topo` / `imagery` / `analysis` / `hydro` / `infra` (accepted but not wired) |
| `--dem-product` | enum | No | `SRTM1` | ✅ | `SRTM1` (30m) / `SRTM3` (90m) |
| `--contour-interval` | float | No | 20 | ✅ | Meters |
| `--concurrency` | int | No | 8 | ✅ | Parallel tile downloads |
| `--batch-size` | int | No | 100 | ✅ | Tiles per batch (new, for large areas) |
| `--batch-delay` | float | No | 2.0 | ✅ | Seconds between batches (new) |
| `--hillshade/--no-hillshade` | flag | No | false | ✅ | Computed hillshade layer |
| `--skip` | list | No | — | ✅ | Comma-separated layers to skip |
| `--quiet/--no-quiet` | flag | No | false | ✅ | Suppress progress |
| `--mgrs` | flag | No | false | ❌ | MGRS grid — uses QGIS native instead |
| `--vegetation` | flag | No | false | ❌ | Vegetation density analysis — not started |
| `--hatch` | flag | No | false | ❌ | Movement vectorization — not started |
| `--urban-hatch` | flag | No | false | ❌ | Urban buildup hatch — not started |
| `--symbology` | enum | No | `2525d` | ❌ | Military symbology standard — not started |
| `--style-dir` | path | No | alongside output | ❌ | Not needed (styles always output alongside) |

---

## 2. Output Format (Diverged from Original Spec)

**Original spec:** Single GeoPackage with all layers merged.

**Actual implementation:** Individual GeoTIFFs + QML styles in `outputs/{name}/`.

Rationale: GPKG raster merging via sqlite3 was unreliable — corrupted layers. Individual GeoTIFFs are more robust, easier to debug, and work directly in QGIS.

```
outputs/{name}/
├── {name}_basemap.tif       Topographic map tiles (RGB)
├── {name}_imagery.tif       Satellite imagery (RGB)
├── {name}_dem.tif           SRTM elevation (float32)
├── {name}_slope.tif         Slope in degrees (float32)
├── {name}_hillshade.tif     Shaded relief (float32)
├── {name}_movement.tif      Military movement class (int8: 0/1/2)
└── styles/
    ├── basemap.qml
    ├── imagery.qml
    ├── dem.qml
    ├── slope.qml
    ├── hillshade.qml
    ├── movement_class.qml
    ├── roads.qml
    └── urban_areas.qml
```

---

## 3. Elevation Data (Diverged from Original Spec)

**Original spec:** `elevation` Python library.

**Actual implementation:** Direct SRTM HGT download from AWS Open Data (`elevation-tiles-prod/skadi/`).

Rationale: The `elevation` library had dependency issues and unreliable merge behavior. Direct download is simpler and more controllable.

---

## 4. Military Symbology Standard

All installation, unit, and facility symbols conform to **MIL-STD-2525D** (US) / **APP-6(D)** (NATO) as specified in **ATP 2-01.3**.

### 4.1 Symbol Generation

- **Library**: `military-symbol` Python package (nwroyer/Python-Military-Symbols)
- **Supports**: NATO APP-6(E) compliant SVG generation from SIDC codes or natural language
- **Status**: Not implemented yet (Phase 2)

### 4.2 SIDC Codes for IPOE-relevant Installations (Symbol Set 20 — Land Installation)

| Feature | OSM Tag | SIDC | Description |
|---------|---------|------|-------------|
| Airport/Airfield | `aeroway=aerodrome` | S2001000000 | Airport symbol |
| Military Airfield | `military=airfield` | S2001000100 | Military aircraft facility |
| Helipad | `aeroway=helipad` | S2001000200 | Helicopter landing area |
| Seaport | `harbour=yes` | S2003000000 | Naval transportation |
| Hospital | `amenity=hospital` | S2005000000 | Medical treatment facility |
| Military Base | `military=base` | S2007000000 | Military installation |
| Barracks | `military=barracks` | S2007000100 | Military housing |
| Training Area | `military=training_area` | S2007000400 | Military training range |
| Ammunition Storage | `military=ammunition` | S2007000200 | Ammo depot |
| Bridge | `bridge=yes` | S2009000000 | Bridge structure |
| Dam | `waterway=dam` | S2010000000 | Dam structure |
| Power Plant | `power=station` | S2011000000 | Electric power facility |
| Water Treatment | `man_made=water_works` | S2013000000 | Water processing |
| Telecommunications | `man_made=communications_tower` | S2015000000 | Comms tower |
| Tunnel | `tunnel=yes` | S2017000000 | Tunnel passage |
| Checkpoint | `barrier=checkpoint` | S2020000000 | Control point |

### 4.3 Urban Buildup Symbology

Per ATP 2-01.3 and standard military map symbology:
- **Urban areas**: Black cross-hatch pattern (45° and 135° intersecting lines)
- **Built-up area boundary**: Thin black outline with cross-hatch fill
- **Individual buildings**: Small black filled rectangles (at higher zoom levels)

---

## 5. Complete OSM Tag Matrix

### 5.1 Aviation

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `aeroway=aerodrome` | Airport/airfield | Polygon | Air LZ, approach/departure paths |
| `aeroway=helipad` | Helipad | Point/Polygon | Rotary-wing LZ |
| `aeroway=airstrip` | Grass strip | Polygon | Tactical LZ |
| `military=airfield` | Military airfield | Polygon | Military aviation |
| `aeroway=runway` | Runway | Line | Surface, length, orientation |
| `aeroway=taxiway` | Taxiway | Line | Airfield layout |

### 5.2 Roads & Trails

| OSM Tag | Feature | Geometry | Classification |
|---------|---------|----------|---------------|
| `highway=motorway` | Highway | Line | Major paved, restricted access |
| `highway=trunk` | Trunk road | Line | Primary paved |
| `highway=primary` | Primary road | Line | Secondary paved |
| `highway=secondary` | Secondary road | Line | Regional paved |
| `highway=tertiary` | Tertiary road | Line | Local paved |
| `highway=unclassified` | Minor road | Line | Unpaved/gravel |
| `highway=residential` | Residential street | Line | Urban minor |
| `highway=track` | Track | Line | Dirt/gravel, 4x4 |
| `highway=path` | Path | Line | Hiking/biking |
| `highway=footway` | Footway | Line | Pedestrian only |
| `highway=bridleway` | Bridleway | Line | Equestrian |
| `highway=steps` | Stairs | Line | Vertical movement |
| `highway=service` | Service road | Line | Access road |

### 5.3 Water / Hydrology

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `waterway=river` | River | Line | Water obstacle, fording |
| `waterway=stream` | Stream | Line | Minor obstacle |
| `waterway=canal` | Canal | Line | Linear obstacle |
| `waterway=ditch` | Ditch | Line | Anti-vehicle |
| `waterway=dam` | Dam | Line/Polygon | Water control, key terrain |
| `natural=water` | Water body | Polygon | Lake, pond, reservoir |
| `natural=wetland` | Wetland | Polygon | Untrafficable |
| `wetland=marsh` | Marsh | Polygon | Impassable to vehicles |
| `wetland=swamp` | Swamp | Polygon | Impassable, concealment |
| `waterway=weir` | Weir | Line | Low dam |
| `natural=spring` | Spring | Point | Water source |
| `man_made=water_well` | Well | Point | Water source |
| `man_made=water_tower` | Water tower | Point | Landmark, water supply |
| `man_made=water_works` | Water treatment | Polygon | Infrastructure |

### 5.4 Infrastructure / Utilities

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `man_made=pipeline` | Pipeline | Line | Gas/oil/water, obstacle/linchpin |
| `pipeline=substance` | (on pipeline) | attr | `gas`, `oil`, `water`, `steam` |
| `power=line` | High-voltage line | Line | EM effects, landmark |
| `power=cable` | Underground cable | Line | Buried utility |
| `man_made=utility_pole` | Utility pole | Point | Comms/power relay |
| `man_made=communications_tower` | Comms tower | Point | C2 infrastructure, landmark |
| `man_made=tower` | Tower | Point | Observation, comms |
| `man_made=chimney` | Smokestack | Point | Landmark |
| `man_made=cooling_tower` | Cooling tower | Point | Power plant indicator |
| `man_made=embankment` | Embankment | Line | Artificial slope |
| `man_made=dyke` | Dyke/levee | Line | Flood control, obstacle |
| `man_made=bridge` | Bridge | Polygon | Key terrain, chokepoint |
| `bridge=yes` | (on way) | attr | Bridge indicator |
| `tunnel=yes` | (on way) | attr | Tunnel indicator |
| `barrier=wall` | Wall | Line | Obstacle |
| `barrier=fence` | Fence | Line | Obstacle/restriction |
| `barrier=gate` | Gate | Point | Controlled access |
| `barrier=bollard` | Bollard | Point | Anti-vehicle |

### 5.5 Buildings & Settlements

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `building=yes` | Building | Polygon | Structure |
| `building=church` | Church | Polygon | Landmark, congregation |
| `building=mosque` | Mosque | Polygon | Landmark |
| `building=synagogue` | Synagogue | Polygon | Landmark |
| `building=hospital` | Hospital | Polygon | Medical |
| `building=school` | School | Polygon | Large structure, rally point |
| `building=industrial` | Industrial | Polygon | Key infrastructure |
| `building=warehouse` | Warehouse | Polygon | Storage, supply |
| `building=dam` | Dam structure | Polygon | Water control |

### 5.6 Places / Administration

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `place=country` | Country | Point | National boundary |
| `place=state` | State/province | Point | Regional boundary |
| `place=city` | City | Point | Major urban area |
| `place=town` | Town | Point | Urban area |
| `place=village` | Village | Point | Settlement |
| `place=hamlet` | Hamlet | Point | Small settlement |
| `place=isolated_dwelling` | Isolated dwelling | Point | Remote structure |
| `place=locality` | Locality | Point | Named place |
| `admin_level=2` | Country boundary | Polygon | National border |
| `admin_level=4` | State boundary | Polygon | State/province border |
| `admin_level=6` | County boundary | Polygon | County border |
| `admin_level=8` | Municipal boundary | Polygon | City/town limit |

### 5.7 Medical / Emergency

| OSM Tag | Feature | Geometry |
|---------|---------|----------|
| `amenity=hospital` | Hospital | Point/Polygon |
| `amenity=clinic` | Clinic | Point/Polygon |
| `amenity=doctors` | Doctor office | Point |
| `amenity=pharmacy` | Pharmacy | Point |
| `amenity=fire_station` | Fire station | Point/Polygon |
| `emergency=ambulance_station` | Ambulance station | Point/Polygon |

### 5.8 Religious / Cultural

| OSM Tag | Feature | Geometry |
|---------|---------|----------|
| `amenity=place_of_worship` | General worship | Point/Polygon |
| `building=church` | Church | Polygon |
| `building=mosque` | Mosque | Polygon |
| `building=synagogue` | Synagogue | Polygon |
| `building=buddhist_temple` | Buddhist temple | Polygon |
| `building=hindu_temple` | Hindu temple | Polygon |
| `amenity=monastery` | Monastery | Point/Polygon |

### 5.9 Military / Defense

| OSM Tag | Feature | Geometry | Notes |
|---------|---------|----------|-------|
| `military=base` | Military base | Polygon | Primary installation |
| `military=airfield` | Military airfield | Polygon | Aviation |
| `military=barracks` | Barracks | Polygon | Housing |
| `military=range` | Firing range | Polygon | Training |
| `military=training_area` | Training area | Polygon | Maneuver |
| `military=ammunition` | Ammo depot | Polygon | Supply |
| `military=bunker` | Bunker | Point/Polygon | Defensive position |
| `military=checkpoint` | Checkpoint | Point | Control point |
| `military=danger_area` | Danger area | Polygon | Restricted |
| `military=office` | Military office | Point/Polygon | Admin |
| `landuse=military` | Military land use | Polygon | General military area |

---

## 6. Output Layers (Complete)

### 6.1 Raster Layers

| Layer Name | Source | Content | Status |
|------------|--------|---------|--------|
| `basemap` | OpenTopoMap / ESRI | Terrain + contour tiles mosaicked | ✅ |
| `imagery` | ESRI World Imagery | Satellite imagery mosaicked | ✅ |
| `dem` | SRTM 30m | Elevation GeoTIFF, float32 | ✅ |
| `hillshade` | Computed from DEM | Hillshade (az=315°, alt=45°) | ✅ |
| `slope` | Computed from DEM | Slope in degrees, float32 | ✅ |
| `movement` | Computed from slope | Unrestricted/Restricted/Highly Restricted (int8) | ✅ |
| `vegetation` | Red/green from imagery | Spectral density index, float32 | ❌ Not started |

### 6.2 Vector Layers — Terrain Analysis (MCOO Components)

Each MCOO component is a **separate toggleable layer** in QGIS. Users can enable/disable individual components independently.

| Layer Name | Geometry | Content | Color | Status |
|------------|----------|---------|-------|--------|
| `contours` | LineString | Contour lines with elevation attr | Brown | ✅ (GDAL wired) |
| `movement_class` | MultiPolygon | Terrain mobility classification | Green hatch per ATP 2-01.3 | ✅ |
| `urban_areas` | MultiPolygon | Built-up area boundaries | Black cross-hatch | ❌ Not started |
| `avenues_of_approach` | LineString | Mounted/dismounted/air avenues | Blue (friendly) / Red (threat) | ❌ Not started |
| `mobility_corridors` | Polygon | Restricted movement corridors | Black | ❌ Not started |
| `key_terrain` | Polygon | Key terrain features | Purple | ❌ Not started |
| `obstacles` | Polygon | Natural and man-made obstacles | Black | ❌ Not started |
| `cover_concealment` | Polygon | Cover and concealment areas | — | ❌ Not started |
| `observation_fire` | Polygon | Observation and fields of fire | — | ❌ Not started |
| `landing_zones` | Point | LZ/DZ locations | — | ❌ Not started |
| `bridge_classifications` | Point | Bridge load classifications | — | ❌ Not started |

### 6.3 Vector Layers — Transportation

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `roads` | LineString | All highway=* features | ❌ Not started |
| `trails` | LineString | path, footway, bridleway, steps | ❌ Not started |

### 6.4 Vector Layers — Hydrology

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `hydro_rivers` | LineString | Rivers, streams, canals, ditches | ❌ Not started |
| `hydro_water` | Polygon | Lakes, reservoirs, ponds | ❌ Not started |
| `hydro_wetlands` | Polygon | Marshes, swamps, bogs | ❌ Not started |
| `hydro_infra` | Point/Polygon | Dams, weirs, wells, water towers | ❌ Not started |

### 6.5 Vector Layers — Infrastructure

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `pipelines` | LineString | Gas, oil, water pipelines | ❌ Not started |
| `power_lines` | LineString | High-voltage transmission lines | ❌ Not started |
| `bridges` | Polygon/Point | Bridge structures | ❌ Not started |
| `tunnels` | LineString/Point | Tunnel entrances/exits | ❌ Not started |
| `barriers` | LineString | Walls, fences, gates | ❌ Not started |
| `comms_towers` | Point | Communications towers | ❌ Not started |
| `water_infra` | Point/Polygon | Water towers, treatment plants | ❌ Not started |

### 6.6 Vector Layers — Installations (Military Symbology)

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `installations` | Point/Polygon | All military=* features | ❌ Not started |
| `medical` | Point/Polygon | Hospitals, clinics, pharmacies | ❌ Not started |
| `religious` | Point/Polygon | Churches, mosques, temples | ❌ Not started |
| `government` | Point/Polygon | Government buildings, embassies | ❌ Not started |

### 6.7 Vector Layers — Settlements & Places

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `places` | Point | Cities, towns, villages, hamlets | ❌ Not started |
| `admin_boundaries` | LineString | Country, state, county borders | ❌ Not started |

### 6.8 Vector Layers — Reference

| Layer Name | Geometry | Content | Status |
|------------|----------|---------|--------|
| `mgrs_grid` | — | 1km MGRS grid | QGIS native (not a layer) |

### 6.9 Composite Layers

| Layer Name | Content | Status |
|------------|---------|--------|
| `composite_topo` | basemap + all vector layers baked to raster | ❌ Not started |
| `composite_imagery` | imagery + vegetation overlay baked to raster | ❌ Not started |

---

## 7. Overpass Query Strategy

Single combined query per bbox to minimize API calls (not implemented yet):

```
[out:json][timeout:120];
(
  // Aviation
  way["aeroway"~"aerodrome|helipad|airstrip"]({{bbox}});
  node["aeroway"~"aerodrome|helipad|airstrip"]({{bbox}});

  // Roads
  way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential|track|path|footway|bridleway|steps|service"]({{bbox}});

  // Hydrology
  way["waterway"]({{bbox}});
  relation["waterway"]({{bbox}});
  way["natural"~"water|wetland"]({{bbox}});
  relation["natural"~"water|wetland"]({{bbox}});
  node["natural"~"water|spring"]({{bbox}});
  node["waterway"~"dam|weir"]({{bbox}});
  node["man_made"~"water_well|water_tower|water_works"]({{bbox}});

  // Infrastructure
  way["man_made"~"pipeline|embankment|dyke|bridge"]({{bbox}});
  way["power"~"line|cable"]({{bbox}});
  node["man_made"~"communications_tower|tower|utility_pole|chimney|cooling_tower"]({{bbox}});
  way["bridge"="yes"]({{bbox}});
  way["tunnel"="yes"]({{bbox}});
  way["barrier"~"wall|fence|gate|bollard"]({{bbox}});
  node["barrier"~"wall|fence|gate|bollard|checkpoint"]({{bbox}});

  // Buildings
  way["building"]({{bbox}});
  node["building"]({{bbox}});

  // Places & Admin
  node["place"~"country|state|city|town|village|hamlet|isolated_dwelling|locality"]({{bbox}});
  way["admin_level"~"2|4|6|8"]({{bbox}});
  relation["admin_level"~"2|4|6|8"]({{bbox}});

  // Medical / Emergency
  node["amenity"~"hospital|clinic|doctors|pharmacy|fire_station"]({{bbox}});
  way["amenity"~"hospital|clinic|fire_station"]({{bbox}});
  node["emergency"~"ambulance_station"]({{bbox}});

  // Religious
  node["amenity"="place_of_worship"]({{bbox}});
  way["amenity"="place_of_worship"]({{bbox}});
  node["building"~"church|mosque|synagogue|buddhist_temple|hindu_temple"]({{bbox}});

  // Military
  way["military"]({{bbox}});
  node["military"]({{bbox}});
  way["landuse"="military"]({{bbox}});

  // Government
  node["amenity"~"government|embassy"]({{bbox}});
  way["amenity"~"government|embassy"]({{bbox}});
);
out body;
>;
out skel qt;
```

---

## 8. Symbology Reference (ATP 2-01.3 / MIL-STD-2525D)

### 8.1 Scale-Dependent Rendering

All features must adapt to zoom level. The QML styles use QGIS scale-based visibility and data-defined overrides. Base scale factor: `sf = 2^(13 - zoom)` (zoom 13 = sf 1.0).

| Feature | Zoom 8–10 | Zoom 11–13 | Zoom 14–15 | Zoom 16–17 |
|---------|-----------|------------|------------|------------|
| **MGRS grid lines** | 10km spacing, no labels | 5km spacing, labels at intersections | 1km spacing, labels at intersections | 500m spacing, labels at intersections |
| **MGRS label size** | hidden | 8pt gray | 10pt gray | 12pt gray |
| **Roads** | motorway/trunk only, 1–2px | +primary/secondary, 1–3px | +tertiary/unclassified, 1–3px | +residential/track, 1–3px |
| **Trails** | hidden | hidden | visible, 1px dashed | visible, 1.5px dashed |
| **Buildings** | hidden | hidden | hidden | visible, black fill |
| **Urban areas** | visible, cross-hatch | visible, cross-hatch | visible, cross-hatch | visible + individual buildings |
| **Contours** | 100m interval | 50m interval | 20m interval | 10m interval |
| **Hydro lines** | rivers only | +canals | +streams | +ditches |
| **Labels (places)** | cities/towns only | +villages | +hamlets | +localities |
| **Installation symbols** | large icons | medium icons | small icons | small icons + names |
| **Hatch patterns** | visible at 1:50k+ | visible at 1:25k+ | always visible | always visible |
| **Power lines** | hidden | visible | visible | visible |
| **Barriers** | hidden | hidden | visible | visible |

### 8.2 Movement Classification (Hatch Patterns) — ATP 2-01.3 MCOO

Per ATP 2-01.3, all movement classification uses **green** symbology:

| Class | Slope | Pattern | Color | Border |
|-------|-------|---------|-------|--------|
| Unrestricted | < 5° | No hatching | Transparent | Green border |
| Restricted | 5–15° | Single diagonal hatch (45°) | Green | Green border |
| Severely Restricted | > 15° | Cross-hatch (45° + 135°) | Dark green | Green border |

Hatch spacing scales with zoom: `base_spacing * 2^(13 - zoom)`.

The vectorized movement layer (`movement_class.gpkg`) renders proper hatch patterns. The raster fallback (`movement.class.tif`) uses pseudocolor.

### MCOO Color Control Measures (ATP 2-01.3 Table 4-4)

| Element | Color | Layer |
|---------|-------|-------|
| Avenue of Approach | Blue (friendly) / Black (neutral) / Red (threat) | `avenues_of_approach` |
| Built-up Area | Black | `urban_areas` |
| Hydrology | Blue | `hydro_water`, `hydro_rivers` |
| Key Terrain | Purple | `key_terrain` |
| Mobility Corridor | Black | `mobility_corridors` |
| Obstacles (natural/man-made) | Black | `obstacles` |
| Restricted Terrain | Green | `movement_class` (restricted) |
| Severely Restricted Terrain | Green | `movement_class` (severely restricted) |

### 8.3 Urban Buildup (Black Cross-Hatch)

Per ATP 2-01.3 and standard military mapping:
- 45° and 135° intersecting black lines
- 1px stroke, 50% opacity
- Applied to all `building=*` polygons and aggregated urban area polygons
- Individual buildings at zoom ≥ 15 shown as solid black rectangles

### 8.4 Vegetation Density (Spectral)

| Index Range | Color | Description |
|-------------|-------|-------------|
| 0.0–0.2 | Red | Bare / urban / burned |
| 0.2–0.4 | Orange-Yellow | Sparse scrub / grassland |
| 0.4–0.6 | Yellow-Green | Moderate vegetation |
| 0.6–0.8 | Green | Dense vegetation |
| 0.8–1.0 | Dark Green | Very dense canopy |

### 8.5 Road Classification

| OSM Type | Color | Width | Pattern |
|----------|-------|-------|---------|
| motorway | Thick red | 3px | Solid |
| trunk | Thick orange | 2.5px | Solid |
| primary | Thick yellow | 2.5px | Solid |
| secondary | Medium yellow | 2px | Solid |
| tertiary | Medium white | 1.5px | Solid |
| unclassified | Thin white | 1px | Solid |
| track | Thin brown | 1px | Dashed |
| residential | Thin white | 1px | Solid |

---

## 9. Data Source Priority

| Layer | Priority 1 (PKI) | Priority 2 (Public Fallback) |
|-------|------------------|------------------------------|
| Basemap | MoW topo REST | OpenTopoMap XYZ |
| Imagery | MoW CIB/CI REST | ESRI World Imagery XYZ |
| Elevation | GRiD DTED | SRTM 30m via AWS SKADi |
| Hydrology | NGA GeoNames WMS | OSM Overpass |
| Roads/Trails | NGA GeoNames WMS | OSM Overpass |
| Place Names | NGA GeoNames REST | OSM Nominatim |

---

## 10. Dependencies

```
# Core
httpx>=0.27
click>=8.1
rich>=13.0

# Raster
rasterio>=1.3
numpy>=1.24
Pillow>=10.0
GDAL (system)         # gdal_contour, gdalbuildvrt, gdal_translate

# Elevation
# Direct SRTM download from AWS (no Python elevation library)

# Vector
geopandas>=0.14
fiona>=1.9
shapely>=2.0
pyproj>=3.6

# Military Symbology
military-symbol>=1.0  # APP-6(D)/MIL-STD-2525D SVG generation (not yet used)

# MGRS
mgrs>=1.2             # MGRS coordinate conversion
```

---

## 11. Implementation Phases

### Phase 1 — Core Infrastructure ✅
- CLI, auth, DEM download, slope, hillshade
- Tile download (topo + imagery) + mosaic
- Individual GeoTIFF output (diverged from GPKG)
- Basic QML styles
- Persistent tile cache
- Batch downloading with retry/backoff
- OpenCode skill for agent-driven usage
- README, published to GitHub

### Phase 2 — OSM Vector Layers ❌ Next
- Overpass query (all tags above)
- Parse into classified GeoDataFrames
- Roads, trails, hydrology, buildings, places, admin boundaries
- Military installation symbol generation via `military-symbol`
- Contour extraction verification

### Phase 3 — Analysis & Symbology ❌
- Vegetation density (red/green spectral)
- Movement classification vectorization + hatch patterns
- Urban buildup black cross-hatch (ATP 2-01.3)
- All QML styles (military standard)

### Phase 4 — Composites & Polish ❌
- Composite topo/imagery baking
- SVG symbol export
- Preview HTML (Leaflet.js)
- README with symbology legend
- Error handling, retry, caching polish

---

## 12. Project Structure

```
IPOEForge/
├── ipoe_forge/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Data source configs, thresholds
│   ├── models.py            # Bbox, AOIMetadata, dataclasses
│   ├── auth.py              # PKI/cert detection + public fallback
│   ├── tile_downloader.py   # XYZ tile fetching + mosaic
│   ├── elevation.py         # DEM download, slope, hillshade, movement
│   ├── geopackager.py       # GPKG assembly (legacy, no longer used in main pipeline)
│   ├── styles.py            # QML style generation
│   ├── osm_features.py      # (not started) Roads, trails, buildings, places
│   ├── hydrology.py         # (not started) OSM water features
│   ├── vegetation.py        # (not started) Red/green spectral density
│   ├── installations.py     # (not started) Military symbol generation
│   └── mgrs_grid.py         # (deleted) MGRS grid — uses QGIS native instead
├── skills/ipoe-forge/
│   └── SKILL.md             # OpenCode skill for agent-driven usage
├── tests/
├── outputs/                 # Generated map packages
├── pyproject.toml
├── SPEC.md                  # This file
├── README.md
├── CONTRIBUTING.md
└── AGENTS.md
```
