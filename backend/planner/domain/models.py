"""Plain data types shared across the domain layer. No I/O, no Django."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

METERS_PER_MILE = 1609.344


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class NormalizedRoute:
    """Provider-agnostic route: one entry per polyline vertex in each list."""

    id: str
    coords: list[tuple[float, float]]  # (lat, lon)
    cum_dist_m: list[float]
    cum_time_s: list[float]

    @property
    def distance_m(self) -> float:
        return self.cum_dist_m[-1]

    @property
    def duration_s(self) -> float:
        return self.cum_time_s[-1]


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


@dataclass(frozen=True)
class RiskAssessment:
    level: Risk
    reasons: list[str] = field(default_factory=list)


@dataclass
class Checkpoint:
    lat: float
    lon: float
    mile: float
    eta: datetime
    weather: Weather | None = None
    risk: RiskAssessment | None = None  # None => forecast unavailable
