import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from planner.domain.models import NormalizedRoute
from planner.providers.routing import _distribute_span_durations, _offset_midpoint, _overlap, parse_here_route
from planner.providers.weather import HourlySeries, round_point

FIXTURES = Path(__file__).parent / "fixtures"
H0 = int(datetime(2026, 11, 1, 0, tzinfo=UTC).timestamp())


def test_parse_here_route_matches_reported_totals():
    data = json.loads((FIXTURES / "here_chicago_milwaukee.json").read_text())
    raw = data["routes"][0]
    route = parse_here_route(raw, "A")
    summary = raw["sections"][0]["summary"]

    assert route.distance_m == pytest.approx(summary["length"], rel=1e-6)
    assert route.duration_s == pytest.approx(summary["duration"], rel=1e-6)
    assert len(route.coords) == len(route.cum_dist_m) == len(route.cum_time_s)
    assert all(b >= a for a, b in zip(route.cum_time_s, route.cum_time_s[1:]))
    assert route.coords[0] == pytest.approx((41.8781, -87.6298), abs=0.01)


def test_span_durations_are_spread_by_distance():
    # Two spans over four segments: first covers segs 0-1, second segs 2-3.
    spans = [{"offset": 0, "duration": 30}, {"offset": 2, "duration": 100}]
    seg_t = _distribute_span_durations(spans, [1, 2, 5, 5], {"duration": 130})
    assert seg_t == pytest.approx([10, 20, 50, 50])


def test_offset_midpoint_is_perpendicular():
    # Due-east trip: offset should move north/south, not east/west.
    lat, lon = _offset_midpoint((0, 0), (0, 10), 0.2)
    assert lon == pytest.approx(5)
    assert lat == pytest.approx(2)


def test_overlap_identical_vs_disjoint():
    a = NormalizedRoute("a", [(0, 0), (0, 1)], [0, 1], [0, 1])
    b = NormalizedRoute("b", [(1, 0), (1, 1)], [0, 1], [0, 1])
    assert _overlap(a, a) == pytest.approx(1)
    assert _overlap(a, b) == 0


def series(**overrides):
    base = dict(
        times=[H0, H0 + 3600, H0 + 7200],
        wind=[10.0, 30.0, 50.0],
        gust=[15.0, 35.0, 55.0],
        rain=[0.0, 0.2, 0.6],
        snow=[0.0, 0.0, 0.0],
    )
    return HourlySeries(**{**base, **overrides})


def at(seconds):
    return datetime.fromtimestamp(H0 + seconds, tz=UTC)


def test_wind_is_interpolated_between_hours():
    assert series().at(at(1800)).wind_mph == pytest.approx(20)


def test_precip_uses_hour_ending_after_eta():
    # 00:30 falls in the hour ending 01:00 → value stamped 01:00.
    assert series().at(at(1800)).rain_in_hr == pytest.approx(0.2)
    # Exactly on the hour uses that hour's value.
    assert series().at(at(3600)).rain_in_hr == pytest.approx(0.2)


def test_outside_forecast_returns_none():
    assert series().at(at(7200 + 1)) is None
    assert series().at(at(-3601)) is None


def test_missing_values_are_treated_as_zero():
    assert series(wind=[None, None, None]).at(at(0)).wind_mph == 0


def test_round_point_snaps_to_grid():
    assert round_point(41.8781, -87.6298) == (41.9, -87.65)
