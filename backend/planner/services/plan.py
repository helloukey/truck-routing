"""Orchestrates a trip plan: routes → checkpoints → weather → risk → ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from planner.domain.models import Checkpoint, NormalizedRoute
from planner.domain.risk import assess
from planner.domain.sampling import sample_checkpoints
from planner.domain.scoring import RouteSummary, recommend, summarize
from planner.providers.routing import HereRoutingClient
from planner.providers.weather import OpenMeteoClient, round_point


@dataclass
class PlannedRoute:
    route: NormalizedRoute
    checkpoints: list[Checkpoint]
    summary: RouteSummary


@dataclass
class TripPlan:
    routes: list[PlannedRoute]
    recommended_id: str
    reasons: list[str]


def plan_trip(
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure: datetime,
    load_lb: float,
    interval_mi: int,
    routing: HereRoutingClient | None = None,
    weather: OpenMeteoClient | None = None,
) -> TripPlan:
    routing = routing or HereRoutingClient()
    weather = weather or OpenMeteoClient()

    routes = routing.get_routes(origin, destination, departure, load_lb)
    checkpoints = {r.id: sample_checkpoints(r, interval_mi, departure) for r in routes}

    # One batched weather lookup for every checkpoint on every route.
    all_points = [round_point(c.lat, c.lon) for cps in checkpoints.values() for c in cps]
    series = weather.get_series(all_points)

    for cps in checkpoints.values():
        for cp in cps:
            cp.weather = series[round_point(cp.lat, cp.lon)].at(cp.eta)
            cp.risk = assess(cp.weather, load_lb) if cp.weather else None

    planned = [PlannedRoute(r, checkpoints[r.id], summarize(r, checkpoints[r.id])) for r in routes]
    best, reasons = recommend([p.summary for p in planned])
    return TripPlan(routes=planned, recommended_id=best.route_id, reasons=reasons)
