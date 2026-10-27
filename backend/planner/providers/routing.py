"""HERE Routing v8 (truck) adapter → NormalizedRoute.

ETA fidelity: we request `spans=dynamicSpeedInfo,length,duration`, which
splits each section wherever the expected speed changes. Each span's duration
is spread over its polyline vertices in proportion to vertex distance.

HERE returns up to 3 routes but often fewer (short or highly constrained
trips). We then synthesize alternatives by routing through a via point offset
perpendicular to the trip, discarding candidates that mostly overlap an
existing route or are unreasonably slow.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import flexpolyline
import httpx
from django.conf import settings
from shapely.geometry import LineString

from planner.domain.models import NormalizedRoute

from .errors import NoRouteError, ProviderError

HERE_ROUTES_URL = "https://router.hereapi.com/v8/routes"
LB_TO_KG = 0.45359237
EARTH_RADIUS_M = 6_371_000

TARGET_ROUTES = 3
# Via-point offsets as a fraction of straight-line trip length (signed = side).
VIA_OFFSETS = (0.2, -0.2, 0.35, -0.35)
ROUTE_IDS = "ABC"  # display ids, in provider order
MAX_OVERLAP = 0.8  # reject a candidate sharing more than this fraction with an existing route
MAX_SLOWDOWN = 1.6  # reject a candidate slower than this multiple of the fastest route
OVERLAP_BUFFER_DEG = 0.005  # ≈ 500 m


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def parse_here_route(route_json: dict, route_id: str) -> NormalizedRoute:
    """Flatten all sections of one HERE route into per-vertex cumulative distance/time."""
    coords: list[tuple[float, float]] = []
    cum_dist: list[float] = []
    cum_time: list[float] = []

    for section in route_json["sections"]:
        pts = [(lat, lon) for lat, lon, *_ in flexpolyline.decode(section["polyline"])]
        seg_d = [haversine_m(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        seg_t = _distribute_span_durations(section.get("spans", []), seg_d, section["summary"])

        start_d = cum_dist[-1] if cum_dist else 0.0
        start_t = cum_time[-1] if cum_time else 0.0
        # Sections share their boundary vertex; only the first section contributes it.
        if not coords:
            coords.append(pts[0])
            cum_dist.append(start_d)
            cum_time.append(start_t)
        # Scale geometry distance so the section total matches HERE's reported length.
        geo_total = sum(seg_d) or 1.0
        scale = section["summary"]["length"] / geo_total
        d, t = start_d, start_t
        for i in range(len(seg_d)):
            d += seg_d[i] * scale
            t += seg_t[i]
            coords.append(pts[i + 1])
            cum_dist.append(d)
            cum_time.append(t)

    if len(coords) < 2:
        raise ProviderError("HERE returned an empty route geometry")
    return NormalizedRoute(id=route_id, coords=coords, cum_dist_m=cum_dist, cum_time_s=cum_time)


def _distribute_span_durations(spans: list[dict], seg_d: list[float], summary: dict) -> list[float]:
    """Seconds for each polyline segment, derived from span durations."""
    n = len(seg_d)
    if not spans:
        total_d = sum(seg_d) or 1.0
        return [summary["duration"] * d / total_d for d in seg_d]

    seg_t = [0.0] * n
    for i, span in enumerate(spans):
        start = span["offset"]
        end = spans[i + 1]["offset"] if i + 1 < len(spans) else n
        if end <= start:
            continue
        span_d = sum(seg_d[start:end])
        for j in range(start, end):
            seg_t[j] = span["duration"] * (seg_d[j] / span_d if span_d else 1 / (end - start))
    return seg_t


class HereRoutingClient:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None):
        self.api_key = api_key or settings.HERE_API_KEY
        if not self.api_key:
            raise ProviderError("HERE_API_KEY is not configured")
        self.http = http or httpx.Client(timeout=20)

    def _request(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure: datetime,
        load_lb: float,
        alternatives: int,
        via: tuple[float, float] | None = None,
    ) -> list[dict]:
        params = {
            "transportMode": "truck",
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "departureTime": departure.isoformat(),
            "return": "polyline,summary",
            "spans": "dynamicSpeedInfo,length,duration",
            "alternatives": alternatives,
            "vehicle[grossWeight]": round(load_lb * LB_TO_KG),
            "apiKey": self.api_key,
        }
        if via:
            params["via"] = f"{via[0]},{via[1]}!passThrough=true"
        try:
            resp = self.http.get(HERE_ROUTES_URL, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"HERE routing request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"HERE routing error {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("routes", [])

    def get_routes(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure: datetime,
        load_lb: float,
    ) -> list[NormalizedRoute]:
        raw = self._request(origin, destination, departure, load_lb, alternatives=TARGET_ROUTES - 1)
        if not raw:
            raise NoRouteError("No truck route found between these locations")
        routes = [parse_here_route(r, ROUTE_IDS[i]) for i, r in enumerate(raw[:TARGET_ROUTES])]

        if len(routes) < TARGET_ROUTES:
            routes += self._synthesize(origin, destination, departure, load_lb, routes)
        return routes[:TARGET_ROUTES]

    def _synthesize(self, origin, destination, departure, load_lb, existing):
        vias = [_offset_midpoint(origin, destination, f) for f in VIA_OFFSETS]

        def fetch(via):
            try:
                found = self._request(origin, destination, departure, load_lb, alternatives=0, via=via)
                return found[0] if found else None
            except ProviderError:
                return None  # a failed alternative must not fail the whole plan

        with ThreadPoolExecutor(max_workers=len(vias)) as pool:
            candidates = [c for c in pool.map(fetch, vias) if c]

        fastest = min(r.duration_s for r in existing)
        accepted: list[NormalizedRoute] = []
        for raw in candidates:
            if len(existing) + len(accepted) >= TARGET_ROUTES:
                break
            cand = parse_here_route(raw, ROUTE_IDS[len(existing) + len(accepted)])
            if cand.duration_s > MAX_SLOWDOWN * fastest:
                continue
            if any(_overlap(cand, r) > MAX_OVERLAP for r in existing + accepted):
                continue
            accepted.append(cand)
        return accepted


def _offset_midpoint(a: tuple[float, float], b: tuple[float, float], fraction: float) -> tuple[float, float]:
    """Point offset perpendicular to segment a→b at its midpoint by fraction × |ab|."""
    mid_lat, mid_lon = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    k = math.cos(math.radians(mid_lat))  # treat lon degrees as shorter at latitude
    dx, dy = (b[1] - a[1]) * k, b[0] - a[0]
    return mid_lat + fraction * dx, mid_lon - fraction * dy / k


def _overlap(candidate: NormalizedRoute, other: NormalizedRoute) -> float:
    """Fraction of candidate's length lying within ~500 m of other."""
    cand = LineString([(lon, lat) for lat, lon in candidate.coords])
    zone = LineString([(lon, lat) for lat, lon in other.coords]).buffer(OVERLAP_BUFFER_DEG)
    return cand.intersection(zone).length / cand.length if cand.length else 1.0
