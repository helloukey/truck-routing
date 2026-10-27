"""HERE Geocoding & Search v7 — address/place lookup for the trip form."""

from __future__ import annotations

import httpx
from django.conf import settings

from .errors import ProviderError

HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
COUNTRIES = "countryCode:USA,CAN"  # risk rules are in US units; keep search on-continent
MAX_RESULTS = 5


def geocode(query: str, http: httpx.Client | None = None) -> list[dict]:
    """[{label, lat, lon}] best matches for a free-text query."""
    if not settings.HERE_API_KEY:
        raise ProviderError("HERE_API_KEY is not configured")
    client = http or httpx.Client(timeout=10)
    try:
        resp = client.get(
            HERE_GEOCODE_URL,
            params={"q": query, "in": COUNTRIES, "limit": MAX_RESULTS, "apiKey": settings.HERE_API_KEY},
        )
    except httpx.HTTPError as exc:
        raise ProviderError(f"HERE geocoding request failed: {exc}") from exc
    if resp.status_code != 200:
        raise ProviderError(f"HERE geocoding error {resp.status_code}: {resp.text[:200]}")
    return [
        {"label": item["title"], "lat": item["position"]["lat"], "lon": item["position"]["lng"]}
        for item in resp.json().get("items", [])
    ]
