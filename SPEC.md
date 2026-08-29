# IPOEForge — Complete Specification v2.1

## Purpose

Automate the creation of IPOE map packages from a single CLI command. Define an MGRS bounding box, get a self-contained GeoPackage with every layer needed for terrain analysis, movement planning, and operational visualization — offline-capable for Army systems, with all symbology conforming to **MIL-STD-2525D / APP-6(D)** per **ATP 2-01.3**.

---

## 1. Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--bbox` | 2 MGRS strings | Yes | — | Top-left and bottom-right MGRS coordinates (4-digit precision, e.g. `18TWL8034 18TWN8834`). Defines the AOI by major Northing/Easting intersections (1km grid squares). |
| `--name` | string | Yes | — | AOI identifier |
| `--output` | path | No | `./{name}.gpkg` | Output GeoPackage path |
| `--zoom` | int | No | 13 | Tile zoom 8–17 |
| `--mode` | enum | No | `auto` | `auto` / `pki` / `public` |
| `--layers` | enum | No | `all` | `all` / `topo` / `imagery` / `analysis` / `hydro` / `infra` |
| `--dem-product` | enum | No | `SRTM1` | `SRTM1` (30m) / `SRTM3` (90m) |
| `--contour-interval` | float | No | 20 | Meters |
| `--concurrency` | int | No | 8 | Parallel tile downloads |
| `--mgrs` | flag | No | false | Include MGRS grid |
| `--vegetation` | flag | No | false | Vegetation density analysis |
| `--hatch` | flag | No | false | Vectorize movement class with hatch patterns |
| `--hillshade` | flag | No | false | Computed hillshade layer |
| `--urban-hatch` | flag | No | false | Urban buildup black cross-hatch overlay |
| `--symbology` | enum | No | `2525d` | `2525d` / `app6d` / `basic` — military symbology standard |
| `--style-dir` | path | No | alongside output | QML style output directory |
| `--skip` | list | No | — | Comma-separated layers to skip |
| `--quiet` | flag | No | false | Suppress progress |

---

## 2. Military Symbology Standard

All installation, unit, and facility symbols conform to **MIL-STD-2525D** (US) / **APP-6(D)** (NATO) as specified in **ATP 2-01.3**.

### 2.1 Symbol Generation

- **Library**: `military-symbol` Python package (nwroyer/Python-Military-Symbols)
- **Supports**: NATO APP-6(E) compliant SVG generation from SIDC codes or natural language
- **Styles**: light, medium, dark, unfilled
- **Usage**: Generate SVG icons for each installation/infrastructure feature, embed as attribute in vector layers

### 2.2 SIDC Codes for IPOE-relevant Installations (Symbol Set 20 — Land Installation)

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

### 2.3 Urban Buildup Symbology

Per ATP 2-01.3 and standard military map symbology:
- **Urban areas**: Black cross-hatch pattern (45° and 135° intersecting lines)
- **Built-up area boundary**: Thin black outline with cross-hatch fill
- **Individual buildings**: Small black filled rectangles (at higher zoom levels)

---

## 3. Complete OSM Tag Matrix

### 3.1 Aviation

| OSM Tag | Feature | Geometry | Military Relevance |
|---------|---------|----------|-------------------|
| `aeroway=aerodrome` | Airport/airfield | Polygon | Air LZ, approach/departure paths |
| `aeroway=helipad` | Helipad | Point/Polygon | Rotary-wing LZ |
| `aeroway=airstrip` | Grass strip | Polygon | Tactical LZ |
| `military=airfield` | Military airfield | Polygon | Military aviation |
| `aeroway=runway` | Runway | Line | Surface, length, orientation |
| `aeroway=taxiway` | Taxiway | Line | Airfield layout |

### 3.2 Roads & Trails

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

### 3.3 Water / Hydrology

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

### 3.4 Infrastructure / Utilities

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

### 3.5 Buildings & Settlements

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

### 3.6 Places / Administration

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

### 3.7 Medical / Emergency

| OSM Tag | Feature | Geometry |
|---------|---------|----------|
| `amenity=hospital` | Hospital | Point/Polygon |
| `amenity=clinic` | Clinic | Point/Polygon |
| `amenity=doctors` | Doctor office | Point |
| `amenity=pharmacy` | Pharmacy | Point |
| `amenity=fire_station` | Fire station | Point/Polygon |
| `emergency=ambulance_station` | Ambulance station | Point/Polygon |

### 3.8 Religious / Cultural

| OSM Tag | Feature | Geometry |
|---------|---------|----------|
| `amenity=place_of_worship` | General worship | Point/Polygon |
| `building=church` | Church | Polygon |
| `building=mosque` | Mosque | Polygon |
| `building=synagogue` | Synagogue | Polygon |
| `building=buddhist_temple` | Buddhist temple | Polygon |
| `building=hindu_temple` | Hindu temple | Polygon |
| `amenity=monastery` | Monastery | Point/Polygon |

### 3.9 Military / Defense

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

## 4. Output Layers (Complete)

### 4.1 Raster Layers

| Layer Name | Source | Content | Transparency |
|------------|--------|---------|-------------|
| `basemap` | OpenTopoMap / MoW | Terrain + contour tiles mosaicked | opaque |
| `imagery` | ESRI / MoW CIB | Satellite imagery mosaicked | opaque |
| `dem` | SRTM 30m | Elevation GeoTIFF, float32 | opaque |
| `hillshade` | Computed from DEM | Hillshade (az=315°, alt=45°) | 40% opacity |
| `slope` | Computed from DEM | Slope in degrees, float32 | opaque |
| `vegetation` | Red/green from imagery | Spectral density index, float32 | opaque |

### 4.2 Vector Layers — Terrain Analysis

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `movement_class` | MultiPolygon | Unrestricted / Restricted / Highly Restricted | Hatch: none / single / double |
| `contours` | LineString | Contour lines with elevation attr | Brown, indexed 2x weight |
| `urban_areas` | MultiPolygon | Built-up area boundaries | **Black cross-hatch** per ATP 2-01.3 |

### 4.3 Vector Layers — Transportation

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `roads` | LineString | All highway=* features | Classified by type (color + width) |
| `trails` | LineString | path, footway, bridleway, steps | Dashed green/brown by type |

### 4.4 Vector Layers — Hydrology

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `hydro_rivers` | LineString | Rivers, streams, canals, ditches | Blue, width by waterway type |
| `hydro_water` | Polygon | Lakes, reservoirs, ponds | Solid blue fill |
| `hydro_wetlands` | Polygon | Marshes, swamps, bogs | Blue stipple/wash |
| `hydro_infra` | Point/Polygon | Dams, weirs, wells, water towers | Blue point symbols |

### 4.5 Vector Layers — Infrastructure

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `pipelines` | LineString | Gas, oil, water pipelines | Dashed, colored by substance |
| `power_lines` | LineString | High-voltage transmission lines | Thin dashed, cross markers |
| `bridges` | Polygon/Point | Bridge structures | Brown outline, label |
| `tunnels` | LineString/Point | Tunnel entrances/exits | Dashed, entrance symbol |
| `barriers` | LineString | Walls, fences, gates | Black dashed/solid by type |
| `comms_towers` | Point | Communications towers | Triangle symbol |
| `water_infra` | Point/Polygon | Water towers, treatment plants | Blue symbol |

### 4.6 Vector Layers — Installations (Military Symbology)

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `installations` | Point/Polygon | All military=* features | **MIL-STD-2525D SIDC symbols** via `military-symbol` lib |
| `medical` | Point/Polygon | Hospitals, clinics, pharmacies | Red cross / medical symbol |
| `religious` | Point/Polygon | Churches, mosques, temples, synagogues | Appropriate religious symbol |
| `government` | Point/Polygon | Government buildings, embassies | Building symbol |

### 4.7 Vector Layers — Settlements & Places

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `places` | Point | Cities, towns, villages, hamlets | Size-scaled dot + label |
| `admin_boundaries` | LineString | Country, state, county borders | Dashed, weight by level |

### 4.8 Vector Layers — Reference

| Layer Name | Geometry | Content | Symbology |
|------------|----------|---------|-----------|
| `mgrs_grid` | LineString | 1km MGRS northing/easting grid lines | Thin gray, labeled at intersections |
| `mgrs_labels` | Point | Northing/easting text labels at grid line intersections | Small gray text, offset from lines |
| `graticule` | LineString | Lat/lon grid | Thin gray dashed |

### 4.9 Composite Layers

| Layer Name | Content |
|------------|---------|
| `composite_topo` | basemap + all vector layers + MGRS + graticule baked to raster |
| `composite_imagery` | imagery + vegetation overlay + all vector layers baked to raster |

### 4.10 Metadata

| Layer Name | Content |
|------------|---------|
| `metadata` | Key-value table: all parameters, sources, timestamps, classification |

---

## 5. Installation Symbol Details

The `installations` layer will include SIDC-encoded attributes for each feature:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sidc` | text | 20-character SIDC code (e.g., `S2007000000`) |
| `feature_type` | text | Human-readable type (e.g., "Military Base") |
| `name` | text | Feature name from OSM |
| `military_type` | text | OSM military=* value |
| `svg_icon` | text | SVG symbol string (light style) for QGIS rendering |
| `affiliation` | text | Unknown/Friend/Neutral (default: "Unknown" for installations) |

The `military-symbol` library will be used at build time to generate SVG icons:
```python
import military_symbol
svg = military_symbol.get_symbol_svg_string_from_name("Friendly Military Base")
```

---

## 6. Overpass Query Strategy

Single combined query per bbox to minimize API calls:

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

## 7. Output Directory Structure

```
co_ao_ipoe/
├── co_ao_ipoe.gpkg           # Main GeoPackage (all layers)
├── styles/
│   ├── movement_class.qml    # Hatch symbology (none / single / double)
│   ├── urban_areas.qml       # Black cross-hatch (ATP 2-01.3)
│   ├── vegetation.qml        # Red→green density ramp
│   ├── roads.qml             # Road classification colors
│   ├── trails.qml            # Trail symbology
│   ├── hydro_rivers.qml      # Blue lines
│   ├── hydro_water.qml       # Blue fill
│   ├── hydro_wetlands.qml    # Blue stipple
│   ├── contours.qml          # Brown contour lines
│   ├── installations.qml     # Military installation symbols
│   ├── medical.qml           # Red cross
│   ├── religious.qml         # Religious symbols
│   ├── pipelines.qml         # Dashed, colored by substance
│   ├── power_lines.qml       # Thin dashed with crosses
│   ├── barriers.qml          # Wall/fence/gate symbology
│   ├── comms_towers.qml      # Tower triangle
│   ├── places.qml            # Settlement labels
│   ├── admin_boundaries.qml  # Dashed borders
│   ├── mgrs_grid.qml         # 1km grid lines with labels
│   └── graticule.qml         # Grid styling
├── symbols/                   # Generated SVG icons per SIDC
│   ├── S2007000000.svg        # Military Base
│   ├── S2001000000.svg        # Airport
│   └── ...
├── preview.html              # Leaflet.js interactive preview
└── README.txt                # Layer descriptions, sources, symbology key
```

---

## 8. Symbology Reference (ATP 2-01.3 / MIL-STD-2525D)

### 8.0 Scale-Dependent Rendering

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

**QML pattern for scale visibility:**
```xml
<rule scalemaxdenom="50000" scalemindenom="1">
  <!-- features visible from 1:1 to 1:50,000 -->
</rule>
```

**Hatch density scales with zoom:**
- Hatch line spacing = `base_spacing * sf` where `base_spacing` is at zoom 13
- At zoom 8: spacing × 8 (coarse hatch)
- At zoom 17: spacing × 0.25 (fine hatch)

### Movement Classification (Hatch Patterns)

| Class | Slope | Pattern | QML Description |
|-------|-------|---------|-----------------|
| Unrestricted | < 5° | No hatching | Transparent fill |
| Restricted | 5–15° | Single diagonal hatch (45°) | 1.5px stroke, 30% opacity, gray |
| Highly Restricted | > 15° | Cross-hatch (45° + 135°) | 1.5px stroke, 40% opacity, dark gray |

### Urban Buildup (Black Cross-Hatch)

Per ATP 2-01.3 and standard military mapping:
- 45° and 135° intersecting black lines
- 1px stroke, 50% opacity
- Applied to all `building=*` polygons and aggregated urban area polygons
- Individual buildings at zoom ≥ 15 shown as solid black rectangles

### Vegetation Density (Spectral)

| Index Range | Color | Description |
|-------------|-------|-------------|
| 0.0–0.2 | Red | Bare / urban / burned |
| 0.2–0.4 | Orange-Yellow | Sparse scrub / grassland |
| 0.4–0.6 | Yellow-Green | Moderate vegetation |
| 0.6–0.8 | Green | Dense vegetation |
| 0.8–1.0 | Dark Green | Very dense canopy |

### Road Classification

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
| Elevation | GRiD DTED | SRTM 30m via `elevation` lib |
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
requests>=2.31

# Raster
rasterio>=1.3
numpy>=1.24
Pillow>=10.0
GDAL (system)         # gdal_contour, ogr2ogr

# Elevation
elevation>=1.1

# Vector
geopandas>=0.14
fiona>=1.9
shapely>=2.0
pyproj>=3.6

# Military Symbology
military-symbol>=1.0  # APP-6(D)/MIL-STD-2525D SVG generation

# Optional
mgrs>=1.2             # MGRS grid
```

---

## 11. Implementation Phases

### Phase 1 — Core Infrastructure
- CLI, auth, DEM download, slope, hillshade
- Tile download (topo + imagery) + mosaic
- Basic GPKG assembly
- Basic QML styles

### Phase 2 — OSM Vector Layers
- Overpass query (all tags above)
- Parse into classified GeoDataFrames
- Roads, trails, hydrology, buildings, places, admin boundaries
- Military installation symbol generation via `military-symbol`
- Contour extraction

### Phase 3 — Analysis & Symbology
- Vegetation density (red/green spectral)
- Movement classification vectorization + hatch patterns
- Urban buildup black cross-hatch (ATP 2-01.3)
- All QML styles (military standard)
- MGRS grid + graticule

### Phase 4 — Composites & Polish
- Composite topo/imagery baking
- SVG symbol export
- Preview HTML (Leaflet.js)
- README with symbology legend
- Error handling, retry, caching

---

## 12. Project Structure

```
ipoe_builder/
├── ipoe_builder/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Data source configs, thresholds
│   ├── models.py            # Bbox, AOIMetadata, dataclasses
│   ├── auth.py              # PKI/cert detection + public fallback
│   ├── tile_downloader.py   # XYZ tile fetching + mosaic
│   ├── elevation.py         # DEM download, slope, contours
│   ├── imagery.py           # Imagery download + vegetation analysis
│   ├── vegetation.py        # Red/green spectral density
│   ├── hydrology.py         # OSM water features
│   ├── osm_features.py      # Roads, trails, buildings, places, infra
│   ├── terrain_analysis.py  # Slope classification + hatch vectorization
│   ├── urban_analysis.py    # Urban buildup detection + cross-hatch
│   ├── installations.py     # Military symbol generation
│   ├── geopackager.py       # Assemble all layers into .gpkg
│   ├── mgrs_grid.py         # MGRS grid generation
│   └── styles/              # QML style templates
├── pyproject.toml
├── requirements.txt
├── SPEC.md                  # This file
└── README.md
```
