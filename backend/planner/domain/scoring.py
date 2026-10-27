"""Per-route risk mileage and route recommendation.

Mile attribution: the segment between consecutive checkpoints takes the worse
of its two endpoint risks (conservative; every mile counted exactly once).
If one endpoint has no forecast the other is used; if neither does, the
segment's miles are counted as "unknown" and excluded from the average.

Ranking (lexicographic, per spec, with No Travel added as a hard first key):
  1. any No Travel miles (routes with them go last)
  2. fewest Severe miles
  3. fewest High miles
  4. lowest distance-weighted average risk
  5. shortest travel time
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import METERS_PER_MILE, Checkpoint, NormalizedRoute, Risk

# Round before comparing so float noise can't flip a genuine tie.
MILE_PRECISION = 1
AVG_PRECISION = 3


@dataclass
class RouteSummary:
    route_id: str
    distance_mi: float
    duration_s: float
    miles_by_risk: dict[Risk, float] = field(default_factory=lambda: {r: 0.0 for r in Risk})
    unknown_miles: float = 0.0
    avg_risk: float = 0.0
    worst: Risk = Risk.LOW

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_risk[Risk.NO_TRAVEL]

    def sort_key(self) -> tuple:
        return (
            round(self.no_travel_miles, MILE_PRECISION) > 0,
            round(self.miles_by_risk[Risk.SEVERE], MILE_PRECISION),
            round(self.miles_by_risk[Risk.HIGH], MILE_PRECISION),
            round(self.avg_risk, AVG_PRECISION),
            self.duration_s,
        )


def _segment_risk(a: Checkpoint, b: Checkpoint) -> Risk | None:
    levels = [c.risk.level for c in (a, b) if c.risk is not None]
    return max(levels) if levels else None


def summarize(route: NormalizedRoute, checkpoints: list[Checkpoint]) -> RouteSummary:
    summary = RouteSummary(
        route_id=route.id,
        distance_mi=route.distance_m / METERS_PER_MILE,
        duration_s=route.duration_s,
    )
    weighted = 0.0
    known = 0.0
    for a, b in zip(checkpoints, checkpoints[1:]):
        miles = b.mile - a.mile
        level = _segment_risk(a, b)
        if level is None:
            summary.unknown_miles += miles
            continue
        summary.miles_by_risk[level] += miles
        weighted += int(level) * miles
        known += miles
        summary.worst = max(summary.worst, level)

    summary.avg_risk = weighted / known if known else 0.0
    return summary


def recommend(summaries: list[RouteSummary]) -> tuple[RouteSummary, list[str]]:
    """Best route plus human-readable reasons comparing it to the runner-up."""
    if not summaries:
        raise ValueError("no routes to rank")
    ranked = sorted(summaries, key=RouteSummary.sort_key)
    best = ranked[0]
    if len(ranked) == 1:
        return best, ["Only route available"]

    reasons = []
    for other in ranked[1:]:
        reasons.append(_explain(best, other))
    if best.no_travel_miles > 0:
        reasons.insert(0, "Warning: every route has No Travel conditions — consider delaying departure")
    return best, reasons


def _explain(best: RouteSummary, other: RouteSummary) -> str:
    """Name the first ranking criterion that separates best from other."""
    b, o = best.sort_key(), other.sort_key()
    name = f"Route {other.route_id}"
    if b[0] != o[0]:
        return f"Avoids {other.no_travel_miles:.0f} No Travel mi on {name}"
    if b[1] != o[1]:
        return f"{b[1]:.0f} Severe mi vs {o[1]:.0f} on {name}"
    if b[2] != o[2]:
        return f"{b[2]:.0f} High mi vs {o[2]:.0f} on {name}"
    if b[3] != o[3]:
        return f"Lower average risk ({b[3]:.2f} vs {o[3]:.2f} on {name})"
    diff_min = (other.duration_s - best.duration_s) / 60
    return f"Same risk profile as {name} but {diff_min:.0f} min faster"
