"""QML style generation for QGIS layers."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _scale_factor(zoom: int) -> float:
    """Scale factor relative to zoom 13 base."""
    return 2.0 ** (13 - zoom)


def _hatch_spacing(zoom: int, base: float = 10.0, bbox_area_deg2: float = 1.0) -> float:
    """Hatch line spacing that scales with zoom and AOI area.

    A 1km² AOI gets tight hatching. A state-wide build gets wide hatching
    so the basemap stays visible underneath.

    Rules of thumb at zoom 13:
      - 1km² (0.01°×0.01°) → base spacing
      - 100km² (0.1°×0.1°) → 3× base
      - 10,000km² (1°×1°)  → 10× base
    """
    spacing = base * _scale_factor(zoom)
    # area^0.3 gives gentle but meaningful scaling
    area_factor = max(1.0, bbox_area_deg2 ** 0.3)
    return spacing * area_factor


def _road_width(road_type: str, zoom: int) -> float:
    """Road width in pixels, scaled by zoom."""
    base_widths = {
        "motorway": 3.0,
        "trunk": 2.5,
        "primary": 2.5,
        "secondary": 2.0,
        "tertiary": 1.5,
        "unclassified": 1.0,
        "residential": 1.0,
        "track": 1.0,
    }
    return base_widths.get(road_type, 1.0) * _scale_factor(zoom)


MOVEMENT_CLASS_QML = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <rasterrenderer type="singlebandpseudocolor" band="1"
    classificationMin="0" classificationMax="2"
    numberOfClasses="3" grayBand="1">
    <rastershader>
      <colorrampshader colorRampType="EXACT" clip="0">
        <colorrampEntry value="0" label="Unrestricted" color="0,0,0,0"/>
        <colorrampEntry value="1" label="Restricted" color="0,128,0,128"/>
        <colorrampEntry value="2" label="Severely Restricted" color="0,100,0,160"/>
      </colorrampshader>
    </rastershader>
  </rasterrenderer>
</qgis>
"""


def _movement_vector_qml(zoom: int, bbox_area_deg2: float = 1.0) -> str:
    """Vectorized movement classification QML — ATP 2-01.3 MCOO compliant.

    Green hatching per doctrine. Only restricted classes shown —
    unrestricted is implied by absence.
    - 1 (Restricted): green diagonal hatch, dark green border
    - 2 (Severely Restricted): green cross-hatch, dark green border
    """
    spacing = _hatch_spacing(zoom, base=50.0, bbox_area_deg2=bbox_area_deg2)
    border_width = max(0.5, 1.0 * _scale_factor(zoom))
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="categorizedSymbol" attr="class">
    <categories>
      <category value="1" label="Restricted" symbol="1"/>
      <category value="2" label="Severely Restricted" symbol="2"/>
    </categories>
    <symbols>
      <symbol type="fill" name="1" alpha="0.35">
        <layer class="SimpleFill">
          <prop v="no" k="style"/>
          <prop v="{border_width}" k="width"/>
          <prop v="0,100,0,255" k="color"/>
          <prop v="solid" k="penstyle"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,128,0,200" k="line_color"/>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="0.45">
        <layer class="SimpleFill">
          <prop v="no" k="style"/>
          <prop v="{border_width}" k="width"/>
          <prop v="0,80,0,255" k="color"/>
          <prop v="solid" k="penstyle"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,100,0,200" k="line_color"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="135" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,100,0,200" k="line_color"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""

URBAN_AREAS_QML = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="singleSymbol">
    <symbols>
      <symbol type="fill" name="0" alpha="0.5">
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1" k="line_width"/>
          <prop v="black" k="line_color"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="135" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1" k="line_width"/>
          <prop v="black" k="line_color"/>
        </layer>
        <layer class="SimpleLine">
          <prop v="0.5" k="line_width"/>
          <prop v="black" k="line_color"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""


def _roads_qml(zoom: int) -> str:
    """Generate roads QML with scale-dependent rules."""
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="categorizedSymbol" attr="highway">
    <categories>
      <category value="motorway" label="Motorway" symbol="0"/>
      <category value="trunk" label="Trunk" symbol="1"/>
      <category value="primary" label="Primary" symbol="2"/>
      <category value="secondary" label="Secondary" symbol="3"/>
      <category value="tertiary" label="Tertiary" symbol="4"/>
      <category value="unclassified" label="Unclassified" symbol="5"/>
      <category value="residential" label="Residential" symbol="6"/>
      <category value="track" label="Track" symbol="7"/>
    </categories>
    <symbols>
      <symbol type="line" name="0" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('motorway', zoom)}" k="line_width"/>
          <prop v="red" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="1" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('trunk', zoom)}" k="line_width"/>
          <prop v="orange" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="2" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('primary', zoom)}" k="line_width"/>
          <prop v="yellow" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="3" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('secondary', zoom)}" k="line_width"/>
          <prop v="yellow" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="4" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('tertiary', zoom)}" k="line_width"/>
          <prop v="white" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="5" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('unclassified', zoom)}" k="line_width"/>
          <prop v="white" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="6" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('residential', zoom)}" k="line_width"/>
          <prop v="white" k="line_color"/>
          <prop v="solid" k="line_style"/>
        </layer>
      </symbol>
      <symbol type="line" name="7" alpha="1">
        <layer class="SimpleLine">
          <prop v="{_road_width('track', zoom)}" k="line_width"/>
          <prop v="brown" k="line_color"/>
          <prop v="dash" k="line_style"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""


def generate_all_styles(
    output_dir: Path,
    zoom: int = 13,
    bbox_area_deg2: float = 1.0,
    layer_prefix: str = "",
) -> None:
    """Generate all QML style files for the given zoom level.

    Writes styles to output_dir/styles/ for organization.
    Also writes matching QML files next to layers for QGIS auto-apply.
    layer_prefix is prepended to auto-apply filenames (e.g. 'pohang_korea_').
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    spacing = _hatch_spacing(zoom, bbox_area_deg2=bbox_area_deg2)

    # Movement class raster (fallback display)
    (output_dir / "movement_class.qml").write_text(MOVEMENT_CLASS_QML)

    # Movement class vector (MCOO hatch patterns)
    (output_dir / "movement_class_vec.qml").write_text(_movement_vector_qml(zoom, bbox_area_deg2))

    # Urban areas
    qml = URBAN_AREAS_QML.format(spacing=spacing)
    (output_dir / "urban_areas.qml").write_text(qml)

    # Roads
    (output_dir / "roads.qml").write_text(_roads_qml(zoom))

    # Raster styles — singleband gray with min/max stretch
    for layer in ("slope", "hillshade", "dem"):
        (output_dir / f"{layer}.qml").write_text(_raster_gray_qml(layer))

    # Multiband color (RGB)
    for layer in ("basemap", "imagery"):
        (output_dir / f"{layer}.qml").write_text(_rgb_raster_qml(layer))

    count = len(list(output_dir.glob("*.qml")))
    logger.info(f"Generated {count} QML styles in {output_dir}")

    # Auto-apply: write QML files next to layer files with matching names
    if layer_prefix and output_dir.parent:
        parent = output_dir.parent
        auto_apply = {
            f"{layer_prefix}movement_class.qml": _movement_vector_qml(zoom, bbox_area_deg2),
            f"{layer_prefix}slope.qml": _raster_gray_qml("slope"),
            f"{layer_prefix}hillshade.qml": _raster_gray_qml("hillshade"),
            f"{layer_prefix}dem.qml": _raster_gray_qml("dem"),
            f"{layer_prefix}basemap.qml": _rgb_raster_qml("basemap"),
            f"{layer_prefix}imagery.qml": _rgb_raster_qml("imagery"),
        }
        for fname, content in auto_apply.items():
            (parent / fname).write_text(content)
        logger.info(f"Wrote {len(auto_apply)} auto-apply QML styles to {parent}")


def _raster_gray_qml(layer_name: str) -> str:
    """Grayscale singleband raster style."""
    return """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <rasterrenderer type="singlebandgray" grayBand="1" gradient="BlackToWhite">
    <min max envelope="0,0,0,0" basedat="1"/>
    <colorramp type="gradient" name="">
      <prop v="0,0,0,255" k="color1"/>
      <prop v="255,255,255,255" k="color2"/>
    </colorramp>
  </rasterrenderer>
  <brightnesscontrast brightness="0" contrast="0"/>
  <huesaturation saturation="0" grayscaleMode="0" colorizeColor="255,128,0,255" colorizeOn="0" colorizeStrength="100"/>
  <rastershader>
    <minmaxpixelvaluescalculation>
      <Extent dataCoordinate="true"/>
    </minmaxpixelvaluescalculation>
  </rastershader>
</qgis>
"""


def _rgb_raster_qml(layer_name: str) -> str:
    """Multiband RGB raster style."""
    return """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <rasterrenderer type="multibandcolor" redBand="1" greenBand="2" blueBand="3"/>
  <brightnesscontrast brightness="0" contrast="0"/>
  <huesaturation saturation="0" grayscaleMode="0" colorizeColor="255,128,0,255" colorizeOn="0" colorizeStrength="100"/>
</qgis>
"""


def _mgrs_grid_qml(zoom: int) -> str:
    """MGRS grid overlay QML with scale-dependent label sizes."""
    label_size = max(8, 14 * _scale_factor(zoom))
    line_width = max(0.3, 0.8 * _scale_factor(zoom))
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="RuleRenderer">
    <rules>
      <rule filter="type='grid_line'" label="Grid Lines">
        <symbol type="line" name="0" alpha="0.5">
          <layer class="SimpleLine">
            <prop v="{line_width}" k="line_width"/>
            <prop v="gray" k="line_color"/>
            <prop v="dash" k="line_style"/>
          </layer>
        </symbol>
      </rule>
      <rule filter="type='grid_label'" label="Grid Labels">
        <symbol type="marker" name="1" alpha="1">
          <layer class="SimpleMarker">
            <prop v="0" k="size"/>
            <prop v="0,0,0,0" k="color"/>
          </layer>
          <layer class="SimpleText">
            <prop v="label" k="Field"/>
            <prop v="{label_size}" k="size"/>
            <prop v="1" k="enabled"/>
            <prop v="black" k="color"/>
            <prop v="Bold" k="weight"/>
            <prop v="Arial" k="family"/>
          </layer>
        </symbol>
      </rule>
    </rules>
  </renderer-v2>
</qgis>
"""
