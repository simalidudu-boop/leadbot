"""
scrapers/overpass.py — OpenStreetMap via Overpass API.

No key required. Tries 4 public mirrors in sequence (they get busy).
Filters out places with any website tag (we want businesses that need one).
"""
from __future__ import annotations

import json
from typing import Iterator

from config import Country, log
from http_client import get_text
from models import Lead


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _build_bbox(country: Country) -> str:
    """Return south,west,north,east string for a country's capital radius."""
    lat_delta = country.bbox_km / 111.32
    lng_delta = country.bbox_km / (111.32 * __cos_deg(country.lat))
    return (f"{country.lat - lat_delta:.5f},{country.lng - lng_delta:.5f},"
            f"{country.lat + lat_delta:.5f},{country.lng + lng_delta:.5f}")


def _cos_deg(deg: float) -> float:
    import math
    return math.cos(deg * math.pi / 180)


# Categories we want — broad enough to catch every "needs a website" business.
OVERPASS_QUERY = (
    '[out:json][timeout:60];'
    "("
    'nwr["craft"]();'                      # all crafts (plumber, electrician, etc.)
    'nwr["shop"]();'                       # all shops
    'nwr["office"]();'                     # all offices
    'nwr["amenity"]();'                    # cafes, restaurants, clinics, etc.
    'nwr["tourism"]();'                    # guesthouses, hotels
    'nwr["leisure"]();'                    # gyms, sports
    'nwr["healthcare"]();'                 # clinics
    ');'
    'out center tags;'
)


def _fetch_overpass(query: str) -> dict | None:
    """Try each mirror until one returns valid JSON."""
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            log.debug("Overpass: trying %s", endpoint)
            r = get_text(endpoint, params={"data": query}, timeout=90)
            if not r or '"elements"' not in r:
                log.debug("Overpass: %s returned no elements", endpoint)
                continue
            return json.loads(r)
        except Exception as e:
            log.debug("Overpass: %s failed: %s", endpoint, e)
    log.warning("All Overpass mirrors failed.")
    return None


def scrape_overpass(settings) -> Iterator[Lead]:
    """Run Overpass for every active country; yield Lead objects."""
    for country in settings.countries:
        bbox = _build_bbox(country)
        # Build a query scoped to this bbox
        query = (
            f'[out:json][timeout:60];'
            f'('
            f'nwr["craft"]({bbox});'
            f'nwr["shop"]({bbox});'
            f'nwr["office"]({bbox});'
            f'nwr["amenity"]({bbox});'
            f'nwr["tourism"]({bbox});'
            f'nwr["leisure"]({bbox});'
            f'nwr["healthcare"]({bbox});'
            f');'
            f'out center tags;'
        )
        log.info("Overpass: %s bbox=%s", country.code, bbox)
        data = _fetch_overpass(query)
        if not data:
            continue
        log.info("Overpass: %s → %d elements", country.code, len(data["elements"]))

        for el in data["elements"]:
            tags = el.get("tags") or {}
            name = tags.get("name")
            if not name:
                continue

            # Skip if any website link present
            if (tags.get("website") or tags.get("contact:website")
                    or tags.get("url")):
                continue

            # Skip infrastructure
            if tags.get("power") or tags.get("landuse"):
                continue

            # Skip branded chains
            if tags.get("brand"):
                continue

            # Build category from tags
            cat_parts = []
            for key in ("craft", "shop", "office", "amenity", "tourism",
                        "leisure", "healthcare"):
                if tags.get(key):
                    cat_parts.append(f"{key}:{tags[key]}")
            category = ", ".join(cat_parts) or "name match"

            # Build address
            addr_bits = [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:suburb"),
                tags.get("addr:city"),
                tags.get("addr:postcode"),
            ]
            address = ", ".join(b for b in addr_bits if b) or f"{country.name} area"

            phone = (tags.get("phone") or tags.get("contact:phone")
                     or tags.get("contact:mobile") or "")
            email = (tags.get("email") or tags.get("contact:email") or "")

            has_social = bool(
                tags.get("contact:facebook") or tags.get("facebook")
                or tags.get("contact:instagram") or tags.get("instagram")
            )

            # Get lat/lon (way/relation use center)
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")

            # If a website tag wasn't found, also try looking for an OSM
            # "contact:website" we may have missed
            yield Lead(
                name=name,
                country=country.code,
                city=tags.get("addr:city") or _nearest_city(country, lat, lon),
                category=category,
                address=address,
                phone=phone,
                email=email,
                website="",
                instagram=tags.get("contact:instagram") or tags.get("instagram") or "",
                facebook=tags.get("contact:facebook") or tags.get("facebook") or "",
                linkedin=tags.get("contact:linkedin") or "",
                tiktok=tags.get("contact:tiktok") or "",
                source="overpass",
            )


def _nearest_city(country: Country, lat, lon) -> str:
    """Cheap nearest-city from the country's city list using lat/lon."""
    if lat is None or lon is None:
        return country.cities[0] if country.cities else country.name
    # Just return the capital for now; can be enriched later
    return country.cities[0] if country.cities else country.name
