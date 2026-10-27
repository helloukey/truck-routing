from datetime import UTC, datetime

from planner.domain.models import METERS_PER_MILE, Checkpoint, NormalizedRoute, Risk, RiskAssessment
from planner.domain.scoring import recommend, summarize

T = datetime(2026, 11, 1, tzinfo=UTC)
L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


def build(route_id, levels, step_mi=10, duration_s=3600):
    """Route whose checkpoints sit every step_mi with the given risk levels (None = no forecast)."""
    miles = [i * step_mi for i in range(len(levels))]
    route = NormalizedRoute(
        id=route_id,
        coords=[(0, 0)] * len(levels),
        cum_dist_m=[m * METERS_PER_MILE for m in miles],
        cum_time_s=[duration_s * i / (len(levels) - 1) for i in range(len(levels))],
    )
    cps = [
        Checkpoint(lat=0, lon=0, mile=m, eta=T, risk=None if lvl is None else RiskAssessment(lvl))
        for m, lvl in zip(miles, levels)
    ]
    return summarize(route, cps)


def test_segment_takes_worse_endpoint():
    s = build("A", [L, H, L])
    assert s.miles_by_risk[H] == 20
    assert s.miles_by_risk[L] == 0
    assert s.worst == H
    assert s.avg_risk == 2


def test_unknown_segments_excluded_from_average():
    s = build("A", [L, None, None, M])
    assert s.miles_by_risk[L] == 10  # one known endpoint is used
    assert s.unknown_miles == 10
    assert s.miles_by_risk[M] == 10
    assert s.avg_risk == 0.5


def test_fewest_severe_beats_everything_below():
    a = build("A", [S, L, L, L], duration_s=1000)  # 10 severe, fastest
    b = build("B", [H, H, H, H], duration_s=9000)  # 0 severe, lots of high
    best, reasons = recommend([a, b])
    assert best.route_id == "B"
    assert "Severe" in reasons[0]


def test_high_miles_break_severe_tie():
    a = build("A", [H, L, L])
    b = build("B", [M, M, M])
    assert recommend([a, b])[0].route_id == "B"


def test_average_risk_breaks_high_tie():
    a = build("A", [L, M, M, M], duration_s=100)  # 30 moderate mi, faster
    b = build("B", [L, L, L, M], duration_s=900)  # 10 moderate mi
    best, reasons = recommend([a, b])
    assert best.route_id == "B"
    assert "average risk" in reasons[0]


def test_duration_is_final_tiebreak():
    a = build("A", [L, L], duration_s=5000)
    b = build("B", [L, L], duration_s=4000)
    best, reasons = recommend([a, b])
    assert best.route_id == "B"
    assert "faster" in reasons[0]


def test_no_travel_route_ranks_last_even_if_otherwise_better():
    a = build("A", [N, L, L, L, L], duration_s=100)
    b = build("B", [S, S, L], duration_s=9000)
    best, reasons = recommend([a, b])
    assert best.route_id == "B"
    assert "No Travel" in reasons[0]


def test_warns_when_all_routes_have_no_travel():
    a = build("A", [N, L])
    b = build("B", [N, N])
    best, reasons = recommend([a, b])
    assert best.route_id == "A"
    assert reasons[0].startswith("Warning")
