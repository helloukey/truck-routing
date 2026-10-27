"""Weather + load risk classification.

Band boundaries: each band is lower-inclusive / upper-exclusive
(e.g. wind 25.0 is Moderate, 34.99 is Moderate, 35.0 is High). The top band
follows the spec literally: wind "≥55" is No Travel, rain/snow use a strict
">" (rain exactly 1.00 in/hr is Severe, 1.01 is No Travel).

Classification uses sustained wind (wind_speed_10m); gusts are informational.
"""

from __future__ import annotations

from .models import Risk, RiskAssessment, Weather

# (upper bound, level) — value below the bound gets that level.
WIND_BANDS = [(25, Risk.LOW), (35, Risk.MODERATE), (45, Risk.HIGH), (55, Risk.SEVERE)]
RAIN_BANDS = [(0.10, Risk.LOW), (0.25, Risk.MODERATE), (0.50, Risk.HIGH)]
SNOW_BANDS = [(0.5, Risk.LOW), (1.0, Risk.MODERATE), (2.0, Risk.HIGH)]
RAIN_SEVERE_MAX = 1.00
SNOW_SEVERE_MAX = 3.0


def _band(value: float, bands: list[tuple[float, Risk]], fallback: Risk) -> Risk:
    for upper, level in bands:
        if value < upper:
            return level
    return fallback


def classify_wind(mph: float) -> Risk:
    return _band(mph, WIND_BANDS, Risk.NO_TRAVEL)


def classify_rain(in_hr: float) -> Risk:
    level = _band(in_hr, RAIN_BANDS, Risk.SEVERE)
    return Risk.NO_TRAVEL if in_hr > RAIN_SEVERE_MAX else level


def classify_snow(in_hr: float) -> Risk:
    level = _band(in_hr, SNOW_BANDS, Risk.SEVERE)
    return Risk.NO_TRAVEL if in_hr > SNOW_SEVERE_MAX else level


def apply_load_rules(wind_mph: float, load_lb: float) -> tuple[Risk, str | None]:
    """Minimum risk level imposed by wind + load, with a reason if any rule fired."""
    if wind_mph >= 55:
        return Risk.NO_TRAVEL, f"Wind {wind_mph:.0f} mph ≥ 55 — no travel for any load"
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        return Risk.NO_TRAVEL, f"Wind {wind_mph:.0f} mph with {load_lb:,.0f} lb load (> 30,000 lb)"
    if 35 <= wind_mph < 45 and load_lb > 40_000:
        return Risk.SEVERE, f"Wind {wind_mph:.0f} mph with {load_lb:,.0f} lb load (> 40,000 lb)"
    return Risk.LOW, None


def assess(weather: Weather, load_lb: float) -> RiskAssessment:
    """Overall risk = worst of wind/rain/snow, escalated by load rules."""
    parts = [
        (classify_wind(weather.wind_mph), f"Wind {weather.wind_mph:.0f} mph"),
        (classify_rain(weather.rain_in_hr), f"Rain {weather.rain_in_hr:.2f} in/hr"),
        (classify_snow(weather.snow_in_hr), f"Snow {weather.snow_in_hr:.2f} in/hr"),
    ]
    level = max(p[0] for p in parts)
    reasons = [f"{text} → {lvl.label}" for lvl, text in parts if lvl > Risk.LOW]

    load_level, load_reason = apply_load_rules(weather.wind_mph, load_lb)
    if load_reason and load_level > level:
        level = load_level
        reasons.append(load_reason)

    return RiskAssessment(level=level, reasons=reasons)
