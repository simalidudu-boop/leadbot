"""
scrapers/geoapify.py — Geoapify Places API.

Free tier: 3,000 credits/day. Each places call costs 1 credit per 20 results.
"""
from __future__ import annotations

import time
from typing import Iterator

from config import log
from http_client import get_json, polite_sleep
from models import Lead


# Categories that cover our 5 countries' small businesses.
# See: https://apidocs.geoapify.com/playground/places/
CATEGORIES = [
    "commercial",                  # everything commercial
    "service",                     # trades, professional services
    "accommodation",               # hotels, guesthouses
    "tourism",                     # tourism-related
    "healthcare",                  # clinics
    "leisure",                     # gyms
    "catering",                    # restaurants
    "education",                   # schools
    "retail",                      # shops
    "beauty",                      # salons
    "automotive",                  # mechanics, dealers
    "building",                    # hardware, construction
    "financial",                   # small loan places
]


def scrape_geoapify(settings) -> Iterator[Lead]:
    if not settings.geoapify_key:
        return
    log.info("Geoapify: starting")

    for country in settings.countries:
        for cat in CATEGORIES:
            try:
                url = "https://api.geoapify.com/v2/places"
                params = {
                    "categories": cat,
                    "filter": f"circle:{country.lng},{country.lat},{country.bbox_km * 1000}",
                    "limit": 20,
                    "apiKey": settings.geoapify_key,
                }
                data = get_json(url, params=params)
                if not data:
                    continue
                features = data.get("features", [])
                log.info("Geoapify %s/%s → %d results",
                         country.code, cat, len(features))

                for f in features:
                    p = f.get("properties") or {}
                    name = p.get("name")
                    if not name:
                        continue
                    website = p.get("website") or ""
                    if website:
                        continue   # has a site → not a lead
                    contact = p.get("contact") or {}
                    email = contact.get("email") or p.get("email") or ""
                    phone = contact.get("phone") or p.get("phone") or ""
                    addr = p.get("formatted") or p.get("address_line1") or ""

                    yield Lead(
                        name=name,
                        country=country.code,
                        city=p.get("city") or p.get("suburb") or country.cities[0],
                        category=p.get("category") or cat,
                        address=addr,
                        phone=phone,
                        email=email,
                        website="",
                        instagram=_social(p, "instagram"),
                        facebook=_social(p, "facebook"),
                        linkedin="",
                        tiktok="",
                        source="geoapify",
                    )
                polite_sleep(0.25)   # respect 5 req/s
            except Exception as e:
                log.warning("Geoapify %s/%s error: %s", country.code, cat, e)


def _social(props, kind) -> str:
    """Geoapify puts social handles under 'datasource.raw' or 'contact'."""
    contact = props.get("contact") or {}
    return contact.get(kind, "") or ""
