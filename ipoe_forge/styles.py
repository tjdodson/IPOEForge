"""QML style generation for QGIS layers."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _scale_factor(zoom: int) -> float:
    """Scale factor relative to zoom 13 base."""
    return 2.0 ** (13 - zoom)


def _hatch_spacing(zoom: int, base: float = 10.0) -> float:
    """Hatch line spacing that scales with zoom."""
    return base * _scale_factor(zoom)


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
  <renderer-v2 type="categorizedSymbol" attr="class">
    <categories>
      <category value="0" label="Unrestricted" symbol="0"/>
      <category value="1" label="Restricted" symbol="1"/>
      <category value="2" label="Highly Restricted" symbol="2"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="0">
        <layer class="SimpleFill">
          <prop v="0" k="style"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="0.3">
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="gray" k="line_color"/>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="0.4">
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="dimgray" k="line_color"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="135" k="line_angle"/>
          <prop v="{spacing}" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="dimgray" k="line_color"/>
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


def generate_all_styles(output_dir: Path, zoom: int = 13) -> None:
    """Generate all QML style files for the given zoom level."""
    output_dir.mkdir(parents=True, exist_ok=True)
    spacing = _hatch_spacing(zoom)

    # Movement class
    qml = MOVEMENT_CLASS_QML.format(spacing=spacing)
    (output_dir / "movement_class.qml").write_text(qml)

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


def _raster_gray_qml(layer_name: str) -> str:
    """Grayscale singleband raster style."""
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
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
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <rasterrenderer type="multibandcolor" redBand="1" greenBand="2" blueBand="3"/>
  <brightnesscontrast brightness="0" contrast="0"/>
  <huesaturation saturation="0" grayscaleMode="0" colorizeColor="255,128,0,255" colorizeOn="0" colorizeStrength="100"/>
</qgis>
"""
