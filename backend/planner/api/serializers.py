from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers
from shapely.geometry import LineString

from planner.domain.models import Risk
from planner.domain.sampling import ALLOWED_INTERVALS_MI
from planner.services.plan import PlannedRoute, TripPlan

MAX_DEPARTURE_AHEAD = timedelta(days=7)  # forecast skill (and our window) fades beyond this
MAX_LOAD_LB = 120_000
GEOMETRY_SIMPLIFY_DEG = 0.0003  # ≈ 30 m — invisible on screen, cuts payload ~10×


class LocationSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True)


class PlanRequestSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=ALLOWED_INTERVALS_MI)

    def validate_departure(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError("Departure must include a timezone offset.")
        now = timezone.now()
        if value < now - timedelta(hours=1):
            raise serializers.ValidationError("Departure cannot be in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Departure must be within the next 7 days (forecast range).")
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if (round(o["lat"], 4), round(o["lon"], 4)) == (round(d["lat"], 4), round(d["lon"], 4)):
            raise serializers.ValidationError("Origin and destination must differ.")
        return attrs


def _risk_name(level: Risk) -> str:
    return level.name.lower()


def _geometry(route) -> list[list[float]]:
    """[[lon, lat, elapsed_s], …] — simplified for display, keeping travel time per vertex.

    Douglas-Peucker keeps a subset of the original vertices, so each kept vertex
    can look up its elapsed time exactly.
    """
    elapsed = {(lon, lat): t for (lat, lon), t in zip(route.coords, route.cum_time_s)}
    line = LineString([(lon, lat) for lat, lon in route.coords]).simplify(GEOMETRY_SIMPLIFY_DEG)
    return [[round(x, 5), round(y, 5), round(elapsed[(x, y)])] for x, y in line.coords]


def _checkpoint(cp) -> dict:
    return {
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "mile": round(cp.mile, 1),
        "eta": cp.eta.isoformat(),
        "weather": None
        if cp.weather is None
        else {
            "wind_mph": round(cp.weather.wind_mph, 1),
            "gust_mph": round(cp.weather.gust_mph, 1),
            "rain_in_hr": round(cp.weather.rain_in_hr, 3),
            "snow_in_hr": round(cp.weather.snow_in_hr, 3),
        },
        "risk": None
        if cp.risk is None
        else {"level": int(cp.risk.level), "label": cp.risk.level.label, "reasons": cp.risk.reasons},
    }


def _route(p: PlannedRoute) -> dict:
    s = p.summary
    return {
        "id": p.route.id,
        "distance_mi": round(s.distance_mi, 1),
        "duration_s": round(s.duration_s),
        "arrival": p.checkpoints[-1].eta.isoformat(),
        "geometry": _geometry(p.route),
        "summary": {
            "miles_by_risk": {_risk_name(r): round(m, 1) for r, m in s.miles_by_risk.items()},
            "unknown_miles": round(s.unknown_miles, 1),
            "avg_risk": round(s.avg_risk, 3),
            "worst": {"level": int(s.worst), "label": s.worst.label},
        },
        "checkpoints": [_checkpoint(c) for c in p.checkpoints],
    }


def serialize_plan(plan: TripPlan) -> dict:
    lats = [lat for p in plan.routes for lat, _ in p.route.coords]
    lons = [lon for p in plan.routes for _, lon in p.route.coords]
    return {
        "recommended_route_id": plan.recommended_id,
        "reasons": plan.reasons,
        "bounds": [min(lons), min(lats), max(lons), max(lats)],
        "routes": [_route(p) for p in plan.routes],
    }


class HeatmapRequestSerializer(serializers.Serializer):
    # Route geometries as returned by /api/plan ([lon, lat, elapsed_s] — extra values ignored).
    lines = serializers.ListField(
        child=serializers.ListField(child=serializers.ListField(child=serializers.FloatField(), min_length=2)),
        min_length=1,
        max_length=5,
    )
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_lines(self, value):
        lines = [[(pt[0], pt[1]) for pt in line] for line in value]
        if any(len(line) < 2 for line in lines):
            raise serializers.ValidationError("Each line needs at least two points.")
        return lines


def serialize_heatmap(hm) -> dict:
    g = hm.grid
    return {
        "start": hm.start.isoformat(),
        "hours": len(hm.risk),
        "grid": {
            "west": g.west,
            "north": g.north,
            "dlon": g.dlon,
            "dlat": g.dlat,
            "cols": g.cols,
            "rows": g.rows,
            "cells": g.cells,
        },
        "risk": hm.risk,
        "wind": hm.wind,
        "rain": hm.rain,
        "snow": hm.snow,
    }
