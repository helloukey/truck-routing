from datetime import UTC, datetime, timedelta

import pytest

from planner.domain.models import METERS_PER_MILE, NormalizedRoute
from planner.domain.sampling import sample_checkpoints

DEPART = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def make_route(segments):
    """segments: list of (miles, minutes); laid out east along the equator-ish."""
    coords, dists, times = [(40.0, -100.0)], [0.0], [0.0]
    for miles, minutes in segments:
        lat, lon = coords[-1]
        coords.append((lat, lon + miles / 50))  # geometry only needs to be monotonic
        dists.append(dists[-1] + miles * METERS_PER_MILE)
        times.append(times[-1] + minutes * 60)
    return NormalizedRoute(id="r", coords=coords, cum_dist_m=dists, cum_time_s=times)


def test_count_and_positions_include_destination():
    route = make_route([(105, 105)])  # 105 mi at 60 mph
    cps = sample_checkpoints(route, 25, DEPART)
    assert [round(c.mile, 3) for c in cps] == [0, 25, 50, 75, 100, 105]
    assert cps[0].eta == DEPART
    assert cps[-1].eta == DEPART + timedelta(minutes=105)


def test_eta_uses_variable_segment_speeds():
    # First 50 mi at 50 mph (60 min), next 50 mi at 25 mph (120 min).
    route = make_route([(50, 60), (50, 120)])
    cps = sample_checkpoints(route, 25, DEPART)
    etas = [(c.eta - DEPART).total_seconds() / 60 for c in cps]
    assert etas == pytest.approx([0, 30, 60, 120, 180])


def test_snaps_tiny_remainder_to_destination():
    route = make_route([(100.1, 100)])  # remainder 0.1 mi < 1% of 25 mi
    cps = sample_checkpoints(route, 25, DEPART)
    assert len(cps) == 5
    assert cps[-1].mile == pytest.approx(100.1)


def test_short_route_has_origin_and_destination():
    route = make_route([(5, 6)])
    cps = sample_checkpoints(route, 50, DEPART)
    assert [round(c.mile, 3) for c in cps] == [0, 5]


def test_interpolates_position_within_segment():
    route = make_route([(20, 20)])
    mid = sample_checkpoints(route, 10, DEPART)[1]
    assert mid.lon == pytest.approx(-100 + 0.2)
