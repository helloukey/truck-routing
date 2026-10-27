"""Regular lat/lon grid covering the corridor around a set of routes.

Cells are aligned to multiples of GRID_STEP so their centers coincide with the
weather lookup grid (no extra rounding). Spacing grows with corridor size so the
number of in-corridor cells stays near TARGET_CELLS regardless of trip length.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, MultiLineString, Point
from shapely.prepared import prep

GRID_STEP = 0.05  # must be a multiple of the weather provider's rounding grid
MIN_SPACING = 0.1  # finer than this is below forecast-model resolution
TARGET_CELLS = 250
BUFFER_MI = 30
MILES_PER_DEG_LAT = 69.0


@dataclass(frozen=True)
class Grid:
    west: float  # center of column 0
    north: float  # center of row 0
    dlon: float
    dlat: float
    cols: int
    rows: int
    cells: list[int]  # row-major indices (row * cols + col) inside the corridor

    def center(self, idx: int) -> tuple[float, float]:
        row, col = divmod(idx, self.cols)
        return round(self.north - row * self.dlat, 4), round(self.west + col * self.dlon, 4)


def _snap(value: float, step: float, up: bool) -> float:
    f = math.ceil if up else math.floor
    return round(f(value / step) * step, 4)


def build_grid(lines: list[list[tuple[float, float]]]) -> Grid:
    """lines: route geometries as [(lon, lat), ...]."""
    lines = [ln for ln in lines if len(ln) >= 2]
    if not lines:
        raise ValueError("at least one route line is required")
    geom = MultiLineString([LineString(ln) for ln in lines])

    mid_lat = (geom.bounds[1] + geom.bounds[3]) / 2
    k = math.cos(math.radians(mid_lat))
    # Buffer in a locally equidistant space (x scaled by cos(lat)), then unscale.
    scaled = MultiLineString([LineString([(x * k, y) for x, y in ln]) for ln in lines])
    corridor_scaled = scaled.buffer(BUFFER_MI / MILES_PER_DEG_LAT)

    spacing = max(MIN_SPACING, math.sqrt(corridor_scaled.area / TARGET_CELLS))
    dlat = _snap(spacing, GRID_STEP, up=True)
    dlon = max(_snap(spacing / k, GRID_STEP, up=True), GRID_STEP)

    minx, miny, maxx, maxy = corridor_scaled.bounds
    west, east = _snap(minx / k, dlon, up=False), _snap(maxx / k, dlon, up=True)
    south, north = _snap(miny, dlat, up=False), _snap(maxy, dlat, up=True)
    cols = round((east - west) / dlon) + 1
    rows = round((north - south) / dlat) + 1

    inside = prep(corridor_scaled)
    cells = [
        r * cols + c
        for r in range(rows)
        for c in range(cols)
        if inside.contains(Point((west + c * dlon) * k, north - r * dlat))
    ]
    return Grid(west=west, north=north, dlon=dlon, dlat=dlat, cols=cols, rows=rows, cells=cells)
