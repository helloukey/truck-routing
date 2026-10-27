"""0–48 h forecast grid over the trip corridor, for the map heatmap + slider.

All hours are returned in one response so the slider never refetches.
Values are hour-major: values[h][i] is the value for grid.cells[i] at hour h.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from planner.domain.corridor import Grid, build_grid
from planner.domain.risk import assess
from planner.providers.weather import OpenMeteoClient

HOURS = 49  # 0..48 inclusive


@dataclass
class Heatmap:
    grid: Grid
    start: datetime
    risk: list[list[int | None]]
    wind: list[list[float | None]]
    rain: list[list[float | None]]
    snow: list[list[float | None]]


def build_heatmap(
    lines: list[list[tuple[float, float]]],
    load_lb: float,
    weather: OpenMeteoClient | None = None,
    now: datetime | None = None,
) -> Heatmap:
    weather = weather or OpenMeteoClient()
    start = (now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
    grid = build_grid(lines)
    points = [grid.center(i) for i in grid.cells]
    series = weather.get_series(points)

    risk, wind, rain, snow = [], [], [], []
    for h in range(HOURS):
        when = start + timedelta(hours=h)
        samples = [series[p].at(when) for p in points]
        risk.append([None if w is None else int(assess(w, load_lb).level) for w in samples])
        wind.append([None if w is None else round(w.wind_mph, 1) for w in samples])
        rain.append([None if w is None else round(w.rain_in_hr, 2) for w in samples])
        snow.append([None if w is None else round(w.snow_in_hr, 2) for w in samples])

    return Heatmap(grid=grid, start=start, risk=risk, wind=wind, rain=rain, snow=snow)
