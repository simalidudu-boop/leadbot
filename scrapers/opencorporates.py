"""
scrapers/opencorporates.py — official company registry search.

Free tier: 200 API calls/month. Even so, very useful for finding real
businesses with registration numbers → high lead score.
"""
from __future__ import annotations

from typing import Iterator

from config import log
from http_client import get_json
from models import Lead


JURISDICTIONS = {
    "ZA": "za",
    "ZW": "zw",
    "ZM": "zm",
    "BW": "bw",
    "KE": "ke",
}


def scrape_opencorporates(settings) -> Iterator[Lead]:
    if not settings.opencorporates_key:
        return
    log.info("OpenCorporates: starting")

    for country in settings.countries:
        jurisdiction = JURISDICTIONS.get(country.code)
        if not jurisdiction:
            continue
        for city in country.cities[:5]:   # budget: top 5 cities per country
            try:
                url = "https://api.opencorporates.com/v0.4/companies/search"
                params = {
                    "q": f"company {city}",
                    "jurisdiction_code": jurisdiction,
                    "per_page": 30,
                    "api_token": settings.opencorporates_key,
                }
                data = get_json(url, params=params)
                if not data:
                    continue
                results = (data.get("results") or {}).get("companies") or []
                log.info("OpenCorporates %s/%s → %d results",
                         country.code, city, len(results))

                for c in results:
                    co = c.get("company") or {}
                    name = co.get("name")
                    if not name:
                        continue
                    addr = (co.get("registered_address") or {}).get("locality") or ""
                    yield Lead(
                        name=name,
                        country=country.code,
                        city=city,
                        category="registered company",
                        address=addr,
                        phone="",
                        email="",
                        website="",
                        instagram="",
                        facebook="",
                        linkedin="",
                        tiktok="",
                        source="opencorporates",
                        registry_hit=True,
                    )
            except Exception as e:
                log.warning("OpenCorporates %s/%s error: %s", country.code, city, e)
