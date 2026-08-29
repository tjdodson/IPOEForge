"""Data source configurations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TileSource:
    name: str
    url_template: str  # {z}/{x}/{y} or {z}/{y}/{x} for ArcGIS
    max_zoom: int = 18
    is_arcgis: bool = False  # ArcGIS uses {z}/{y}/{x} order
    needs_auth: bool = False
    attribution: str = ""


# --- Public / Unclassified Sources ---
PUBLIC_SOURCES = {
    "topo": TileSource(
        name="OpenTopoMap",
        url_template="https://tile.opentopomap.org/{z}/{x}/{y}.png",
        max_zoom=17,
        attribution="© OpenStreetMap contributors, SRTM | CC-BY-SA",
    ),
    "imagery": TileSource(
        name="ESRI World Imagery",
        url_template="https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        max_zoom=19,
        is_arcgis=True,
        attribution="© Esri, Maxar, Earthstar Geographics",
    ),
}

# --- NGA / PKI Sources ---
NGA_SOURCES = {
    "topo_mow": TileSource(
        name="MoW Topographic",
        url_template="https://map.nga.mil/arcgis/rest/services/mow/base/MapServer/tile/{z}/{y}/{x}",
        max_zoom=19,
        is_arcgis=True,
        needs_auth=True,
        attribution="© NGA",
    ),
    "imagery_mow": TileSource(
        name="MoW Imagery",
        url_template="https://map.nga.mil/arcgis/rest/services/mow/imagery/MapServer/tile/{z}/{y}/{x}",
        max_zoom=19,
        is_arcgis=True,
        needs_auth=True,
        attribution="© NGA",
    ),
}

# --- Elevation Sources ---
ELEVATION = {
    "srtm30": {
        "product": "SRTM1",
        "description": "SRTM 30m Global 1 arc-second V003",
    },
    "srtm90": {
        "product": "SRTM3",
        "description": "SRTM 90m Digital Elevation Database v4.1",
    },
}

# --- OSM Overpass ---
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# --- Terrain classification thresholds (Army movement standards) ---
SLOPE_THRESHOLDS = {
    "unrestricted_max": 5.0,
    "restricted_max": 15.0,
    "highly_restricted_min": 15.0,
}
