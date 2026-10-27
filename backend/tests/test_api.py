"""End-to-end /api/plan with routing and weather providers stubbed."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from planner.domain.models import METERS_PER_MILE, NormalizedRoute
from planner.providers.errors import NoRouteError
from planner.providers.weather import HourlySeries


def straight_route(route_id, miles, hours, lat):
    n = 11
    return NormalizedRoute(
        id=route_id,
        coords=[(lat, -100 + i * 0.1) for i in range(n)],
        cum_dist_m=[miles * METERS_PER_MILE * i / (n - 1) for i in range(n)],
        cum_time_s=[hours * 3600 * i / (n - 1) for i in range(n)],
    )


class StubRouting:
    def __init__(self, routes=None, error=None):
        self.routes, self.error = routes, error

    def get_routes(self, *args):
        if self.error:
            raise self.error
        return self.routes


class StubWeather:
    """Windy (40 mph) north of lat 41, calm elsewhere."""

    def get_series(self, points):
        start = int((timezone.now() - timedelta(hours=2)).timestamp()) // 3600 * 3600
        times = [start + h * 3600 for h in range(72)]
        return {
            p: HourlySeries(times, [40.0 if p[0] > 41 else 5.0] * 72, [0.0] * 72, [0.0] * 72, [0.0] * 72)
            for p in points
        }


@pytest.fixture
def payload():
    return {
        "origin": {"lat": 40.5, "lon": -100},
        "destination": {"lat": 40.5, "lon": -99},
        "departure": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_lb": 45_000,
        "interval_mi": 10,
    }


def post(payload, monkeypatch, routing):
    monkeypatch.setattr("planner.services.plan.HereRoutingClient", lambda: routing)
    monkeypatch.setattr("planner.services.plan.OpenMeteoClient", lambda: StubWeather())
    return APIClient().post("/api/plan", payload, format="json")


def test_plan_recommends_safer_route_over_faster(payload, monkeypatch):
    fast_windy = straight_route("A", 50, 1, lat=41.5)  # 40 mph + 45k lb → Severe
    slow_calm = straight_route("B", 60, 1.5, lat=40.5)
    resp = post(payload, monkeypatch, StubRouting([fast_windy, slow_calm]))

    assert resp.status_code == 200
    body = resp.json()
    assert body["recommended_route_id"] == "B"
    windy = next(r for r in body["routes"] if r["id"] == "A")
    assert windy["summary"]["miles_by_risk"]["severe"] == 50
    assert windy["checkpoints"][0]["risk"]["label"] == "Severe"
    assert "40,000" in " ".join(windy["checkpoints"][0]["risk"]["reasons"])
    assert len(windy["checkpoints"]) == 6
    assert len(body["bounds"]) == 4


def test_no_route_returns_422(payload, monkeypatch):
    resp = post(payload, monkeypatch, StubRouting(error=NoRouteError("none")))
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("interval_mi", 15),
        ("load_lb", -1),
        ("departure", "2020-01-01T00:00:00Z"),
        ("departure", "2030-01-01T00:00:00"),  # naive and too far ahead
    ],
)
def test_validation_errors(payload, monkeypatch, field, value):
    payload[field] = value
    resp = post(payload, monkeypatch, StubRouting([]))
    assert resp.status_code == 400
    assert field in resp.json()


def test_same_origin_and_destination_rejected(payload, monkeypatch):
    payload["destination"] = payload["origin"]
    assert post(payload, monkeypatch, StubRouting([])).status_code == 400
