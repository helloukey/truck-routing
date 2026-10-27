"""Open-Meteo hourly forecast client.

Many locations are fetched per request (Open-Meteo accepts comma-separated
coordinates). Locations are rounded to GRID_DEG so nearby checkpoints share a
lookup, and each location's series is cached for CACHE_TTL_S.

Units: wind in mph, precipitation in inches. Hourly rain/showers/snowfall are
totals for the *preceding* hour, so an hourly value is already in/hr.
"""

from __future__ import annotations

import bisect
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import httpx
from django.core.cache import cache

from planner.domain.models import Weather

from .errors import ProviderError

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
GRID_DEG = 0.05
BATCH_SIZE = 100  # locations per request; keeps URLs well under length limits
CACHE_TTL_S = 30 * 60
FORECAST_DAYS = 14  # Open-Meteo bills >2 weeks as extra calls

Point = tuple[float, float]


def round_point(lat: float, lon: float) -> Point:
    return (round(round(lat / GRID_DEG) * GRID_DEG, 4), round(round(lon / GRID_DEG) * GRID_DEG, 4))


@dataclass(frozen=True)
class HourlySeries:
    times: list[int]  # unix seconds, hourly, ascending
    wind: list[float]
    gust: list[float]
    rain: list[float]  # rain + showers
    snow: list[float]

    def at(self, when: datetime) -> Weather | None:
        """Weather at an arbitrary instant, or None if outside the forecast.

        Wind (instantaneous) is linearly interpolated between bracketing hours.
        Precipitation uses the hour *ending* at or after `when`, since each
        hourly precip value is the total of the preceding hour.
        """
        ts = when.timestamp()
        if not self.times or ts < self.times[0] - 3600 or ts > self.times[-1]:
            return None
        hi = min(bisect.bisect_left(self.times, ts), len(self.times) - 1)
        lo = max(hi - 1, 0)
        span = self.times[hi] - self.times[lo]
        f = 0.0 if span == 0 else min(max((ts - self.times[lo]) / span, 0.0), 1.0)

        def lerp(vals):
            return _num(vals[lo]) + f * (_num(vals[hi]) - _num(vals[lo]))

        return Weather(
            wind_mph=lerp(self.wind),
            gust_mph=lerp(self.gust),
            rain_in_hr=_num(self.rain[hi]),
            snow_in_hr=_num(self.snow[hi]),
        )


def _num(v) -> float:
    return 0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def parse_location(loc: dict) -> HourlySeries:
    h = loc["hourly"]
    rain = [_num(r) + _num(s) for r, s in zip(h["rain"], h["showers"])]
    return HourlySeries(
        times=h["time"], wind=h["wind_speed_10m"], gust=h["wind_gusts_10m"], rain=rain, snow=h["snowfall"]
    )


class OpenMeteoClient:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=30)

    def get_series(self, points: list[Point]) -> dict[Point, HourlySeries]:
        """Hourly series for each (already-rounded) point, from cache or API."""
        unique = list(dict.fromkeys(points))
        result: dict[Point, HourlySeries] = {}
        missing = []
        for p in unique:
            hit = cache.get(_cache_key(p))
            if hit is not None:
                result[p] = hit
            else:
                missing.append(p)

        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for batch, series in zip(batches, pool.map(self._fetch_batch, batches)):
                for p, s in zip(batch, series):
                    cache.set(_cache_key(p), s, CACHE_TTL_S)
                    result[p] = s
        return result

    def _fetch_batch(self, batch: list[Point]) -> list[HourlySeries]:
        params = {
            "latitude": ",".join(str(p[0]) for p in batch),
            "longitude": ",".join(str(p[1]) for p in batch),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "forecast_days": FORECAST_DAYS,
        }
        try:
            resp = self.http.get(OPEN_METEO_URL, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Open-Meteo request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Open-Meteo error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(batch):
            raise ProviderError("Open-Meteo returned an unexpected number of locations")
        return [parse_location(loc) for loc in locations]


def _cache_key(p: Point) -> str:
    return f"wx:v1:{p[0]}:{p[1]}"
