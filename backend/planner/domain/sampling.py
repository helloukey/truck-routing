"""Place checkpoints every N miles along a route and compute each one's ETA.

ETAs come from the provider's per-vertex cumulative travel time, so highway vs
urban speed differences are preserved (no constant-speed assumption).
"""

from __future__ import annotations

import bisect
from datetime import datetime, timedelta

from .models import METERS_PER_MILE, Checkpoint, NormalizedRoute

ALLOWED_INTERVALS_MI = (10, 25, 50)


def _interpolate(route: NormalizedRoute, target_m: float) -> tuple[float, float, float]:
    """(lat, lon, elapsed_s) at distance target_m along the route."""
    dists = route.cum_dist_m
    i = bisect.bisect_right(dists, target_m)
    if i <= 0:
        lat, lon = route.coords[0]
        return lat, lon, route.cum_time_s[0]
    if i >= len(dists):
        lat, lon = route.coords[-1]
        return lat, lon, route.cum_time_s[-1]

    d0, d1 = dists[i - 1], dists[i]
    f = 0.0 if d1 == d0 else (target_m - d0) / (d1 - d0)
    (lat0, lon0), (lat1, lon1) = route.coords[i - 1], route.coords[i]
    t0, t1 = route.cum_time_s[i - 1], route.cum_time_s[i]
    return lat0 + f * (lat1 - lat0), lon0 + f * (lon1 - lon0), t0 + f * (t1 - t0)


def sample_checkpoints(
    route: NormalizedRoute, interval_mi: float, departure: datetime
) -> list[Checkpoint]:
    """Checkpoints at 0, N, 2N, … miles plus the destination."""
    if interval_mi <= 0:
        raise ValueError("interval_mi must be positive")

    step_m = interval_mi * METERS_PER_MILE
    total_m = route.distance_m
    targets = [k * step_m for k in range(int(total_m // step_m) + 1)]
    # Always end at the destination; if the last mark is within 1% of a step of
    # it, snap that mark to the destination instead of adding a sliver segment.
    if len(targets) == 1 or total_m - targets[-1] > 0.01 * step_m:
        targets.append(total_m)
    else:
        targets[-1] = total_m

    checkpoints = []
    for t in targets:
        lat, lon, elapsed = _interpolate(route, t)
        checkpoints.append(
            Checkpoint(
                lat=lat,
                lon=lon,
                mile=t / METERS_PER_MILE,
                eta=departure + timedelta(seconds=elapsed),
            )
        )
    return checkpoints
