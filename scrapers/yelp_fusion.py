"""
scrapers/yelp_fusion.py — Yelp Fusion API.

Free tier: 500 calls/day. Excellent for hospitality, services, retail.
"""
from __future__ import annotations

from typing import Iterator

from config import log
from http_client import get_json
from models import Lead


def scrape_yelp(settings) -> Iterator[Lead]:
    if not settings.yelp_api_key:
        return
    log.info("Yelp: starting")

    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}

    for country in settings.countries:
        # Country-specific Yelp coverage is patchy. Try a couple of terms.
        terms = ["restaurant", "salon", "plumber", "electrician", "guesthouse",
                 "mechanic", "cafe", "bakery", "butchery", "barber"]
        for term in terms[:5]:   # budget: 5 terms per country
            for city in country.cities[:3]:
                try:
                    data = get_json(
                        "https://api.yelp.com/v3/businesses/search",
                        params={
                            "term": term,
                            "location": f"{city}, {country.name}",
                            "limit": 20,
                        },
                        headers=headers,
                    )
                    if not data:
                        continue
                    for biz in data.get("businesses", []):
                        name = biz.get("name")
                        if not name:
                            continue
                        if biz.get("url") and "yelp.com" in biz["url"]:
                            pass   # yelp url is not their own website
                        # only flag if they have their OWN website
                        if biz.get("website"):
                            continue
                        loc = biz.get("location") or {}
                        addr = ", ".join(loc.get("display_address") or [])

                        yield Lead(
                            name=name,
                            country=country.code,
                            city=city,
                            category=", ".join(biz.get("categories") or []) or term,
                            address=addr,
                            phone=biz.get("phone") or "",
                            email="",
                            website="",
                            instagram="",
                            facebook="",
                            linkedin="",
                            tiktok="",
                            source="yelp",
                        )
                except Exception as e:
                    log.warning("Yelp %s/%s/%s error: %s",
                                country.code, city, term, e)
