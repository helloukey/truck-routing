import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    # Throttle counters and weather series live in the cache; isolate tests.
    cache.clear()
    yield
    cache.clear()
