from datetime import UTC, datetime

import pytest

from planner.domain.corridor import GRID_STEP, TARGET_CELLS, build_grid
from planner.providers.weather import HourlySeries, round_point
from planner.services.heatmap import HOURS, build_heatmap


def is_multiple(value, step):
    return abs(value / step - round(value / step)) < 1e-6


@pytest.mark.parametrize(
    "line",
    [
        [(-87.6, 41.9), (-105.0, 39.7)],  # ~1000 mi
        [(-87.6, 41.9), (-87.9, 43.0)],  # ~90 mi
    ],
)
def test_grid_is_aligned_bounded_and_covers_route(line):
    g = build_grid([line])
    assert 0 < len(g.cells) <= TARGET_CELLS * 1.5
    assert all(is_multiple(v, GRID_STEP) for v in (g.west, g.north, g.dlon, g.dlat))
    centers = {g.center(i) for i in g.cells}
    # Cell centers are already on the weather grid.
    assert all(round_point(*c) == c for c in centers)
    # Every route vertex has an in-corridor cell nearby.
    for lon, lat in line:
        assert any(abs(lat - c[0]) <= g.dlat and abs(lon - c[1]) <= g.dlon for c in centers)


def test_grid_rejects_empty_input():
    with pytest.raises(ValueError):
        build_grid([[(0, 0)]])


class FlatWeather:
    def get_series(self, points):
        start = int(datetime(2026, 11, 1, tzinfo=UTC).timestamp())
        times = [start + h * 3600 for h in range(24)]  # only 24 h available
        return {p: HourlySeries(times, [50.0] * 24, [0.0] * 24, [0.0] * 24, [0.0] * 24) for p in points}


def test_heatmap_applies_load_and_marks_hours_beyond_forecast():
    hm = build_heatmap(
        [[(-87.6, 41.9), (-87.9, 43.0)]],
        load_lb=35_000,
        weather=FlatWeather(),
        now=datetime(2026, 11, 1, 0, 30, tzinfo=UTC),
    )
    assert len(hm.risk) == HOURS
    assert set(hm.risk[0]) == {4}  # 50 mph + >30k lb → No Travel
    assert set(hm.risk[40]) == {None}
