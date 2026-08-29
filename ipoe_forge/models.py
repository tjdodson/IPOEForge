"""Core data models."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TileFormat(Enum):
    XYZ = "xyz"
    TMS = "tms"


class AuthMode(Enum):
    PKI = "pki"
    PUBLIC = "public"
    AUTO = "auto"


class LayerSet(Enum):
    ALL = "all"
    TOPO = "topo"
    IMAGERY = "imagery"
    ANALYSIS = "analysis"
    HYDRO = "hydro"
    INFRA = "infra"


@dataclass(frozen=True)
class Bbox:
    """Bounding box in WGS84 (lon/lat). Convention: west, south, east, north."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if self.west >= self.east:
            raise ValueError(f"west ({self.west}) must be < east ({self.east})")
        if self.south >= self.north:
            raise ValueError(f"south ({self.south}) must be < north ({self.north})")

    @property
    def width_deg(self) -> float:
        return self.east - self.west

    @property
    def height_deg(self) -> float:
        return self.north - self.south

    @property
    def center(self) -> tuple[float, float]:
        return ((self.west + self.east) / 2, (self.south + self.north) / 2)

    def pad(self, margin_deg: float) -> Bbox:
        return Bbox(
            west=self.west - margin_deg,
            south=self.south - margin_deg,
            east=self.east + margin_deg,
            north=self.north + margin_deg,
        )

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


@dataclass
class TileCoord:
    z: int
    x: int
    y: int


@dataclass
class TileGrid:
    """Precomputed tile coordinates for a bbox at a given zoom level."""

    zoom: int
    tiles: list[TileCoord] = field(default_factory=list)

    @classmethod
    def from_bbox(cls, bbox: Bbox, zoom: int) -> TileGrid:
        """Convert a WGS84 bounding box to XYZ tile coordinates."""
        n = 2**zoom

        def lon_to_x(lon: float) -> int:
            return int((lon + 180.0) / 360.0 * n)

        def lat_to_y(lat: float) -> int:
            lat_rad = math.radians(lat)
            return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

        x_min = lon_to_x(bbox.west)
        x_max = lon_to_x(bbox.east)
        y_min = lat_to_y(bbox.north)  # north = lower y
        y_max = lat_to_y(bbox.south)  # south = higher y

        tiles = []
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tiles.append(TileCoord(z=zoom, x=x, y=y))

        return cls(zoom=zoom, tiles=tiles)


@dataclass
class AOIMetadata:
    """Metadata describing an Area of Interest."""

    name: str
    bbox: Bbox
    zoom: int = 12
    output: Path | None = None
    mgrs: bool = False
    layers: LayerSet = LayerSet.ALL
    auth_mode: AuthMode = AuthMode.AUTO

    @property
    def output_path(self) -> Path:
        if self.output:
            return self.output
        return Path(f"{self.name}.gpkg")
