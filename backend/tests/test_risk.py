import pytest

from planner.domain.models import Risk, Weather
from planner.domain.risk import assess, classify_rain, classify_snow, classify_wind

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


@pytest.mark.parametrize(
    "mph,expected",
    [(0, L), (24.99, L), (25, M), (34.99, M), (35, H), (44.99, H), (45, S), (54.99, S), (55, N), (80, N)],
)
def test_wind_bands(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "inches,expected",
    [(0, L), (0.099, L), (0.10, M), (0.249, M), (0.25, H), (0.499, H), (0.50, S), (1.00, S), (1.001, N)],
)
def test_rain_bands(inches, expected):
    assert classify_rain(inches) == expected


@pytest.mark.parametrize(
    "inches,expected",
    [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N)],
)
def test_snow_bands(inches, expected):
    assert classify_snow(inches) == expected


def wx(wind=0.0, rain=0.0, snow=0.0):
    return Weather(wind_mph=wind, gust_mph=wind, rain_in_hr=rain, snow_in_hr=snow)


@pytest.mark.parametrize(
    "wind,load,expected",
    [
        # ≥55 mph: No Travel regardless of load
        (55, 0, N),
        (60, 10_000, N),
        # 45–54 mph: No Travel only above 30,000 lb
        (45, 30_000, S),
        (45, 30_001, N),
        (54.9, 45_000, N),
        # 35–44 mph: Severe only above 40,000 lb
        (35, 40_000, H),
        (35, 40_001, S),
        (44.9, 80_000, S),
        # below 35 mph: load is irrelevant
        (34.9, 80_000, M),
    ],
)
def test_load_rules(wind, load, expected):
    assert assess(wx(wind=wind), load).level == expected


def test_overall_is_worst_condition():
    result = assess(wx(wind=10, rain=0.3, snow=0.6), load_lb=20_000)
    assert result.level == H
    assert any("Rain" in r for r in result.reasons)
    assert any("Snow" in r for r in result.reasons)


def test_load_rule_does_not_downgrade_precip():
    # Rain is No Travel; a Severe load rule must not lower it.
    assert assess(wx(wind=40, rain=1.5), load_lb=50_000).level == N


def test_calm_weather_has_no_reasons():
    result = assess(wx(wind=5), load_lb=80_000)
    assert result.level == L
    assert result.reasons == []
