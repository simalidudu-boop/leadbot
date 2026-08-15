"""
scrapers/yellowpages.py — scrape country yellow pages (HTML).

No API, but the structure of yellowpages.co.za etc. is fairly stable.
If a site blocks us or restructures, the scraper fails silently.
"""
from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

from config import log
from http_client import get_text
from models import Lead

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().\-]{7,}\d)")


def scrape_yellowpages(settings) -> Iterator[Lead]:
    log.info("Yellow Pages: starting")
    for country in settings.countries:
        if not country.yellowpages_url:
            continue
        for term in ("plumber", "electrician", "restaurant", "salon", "mechanic"):
            for city in country.cities[:2]:   # budget: 2 cities per country
                yield from _scrape_listing(country, term, city)


def _scrape_listing(country, term: str, city: str) -> Iterator[Lead]:
    """
    Try the search page for a term in a city. Most yellow pages sites use
    ?what=&where= style URLs.
    """
    candidates = [
        f"{country.yellowpages_url}search?what={quote_plus(term)}&where={quote_plus(city)}",
        f"{country.yellowpages_url}search?searchTerm={quote_plus(term)}&location={quote_plus(city)}",
        f"{country.yellowpages_url}{quote_plus(term)}/{quote_plus(city)}",
    ]
    for url in candidates:
        try:
            html = get_text(url, timeout=20)
            if not html or len(html) < 500:
                continue
            soup = BeautifulSoup(html, "lxml")
            # Look for typical business-listing patterns
            for item in soup.select("div.listing, div.result, article.business, "
                                    "div.business, li.business"):
                name_el = (item.select_one("h2 a, h3 a, .name, .business-name")
                           or item.select_one("a"))
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name or len(name) < 3:
                    continue
                # Detail page
                detail_href = name_el.get("href", "")
                detail_url = urljoin(url, detail_href) if detail_href else None

                address = ""
                addr_el = item.select_one(".address, .addr, .location")
                if addr_el:
                    address = addr_el.get_text(" ", strip=True)

                phone = ""
                phone_el = item.select_one(".phone, .tel")
                if phone_el:
                    phone = phone_el.get_text(strip=True)

                email = ""
                # Most yellow pages don't show email on listing — try detail page
                if detail_url:
                    detail_html = get_text(detail_url, timeout=20)
                    if detail_html:
                        m = EMAIL_RE.search(detail_html)
                        if m:
                            email = m.group(0)
                        mp = PHONE_RE.search(detail_html)
                        if mp and not phone:
                            phone = mp.group(1).strip()

                # Look for any link that's clearly a business site
                website = ""
                for a in item.select("a[href]"):
                    href = a.get("href", "")
                    if not href:
                        continue
                    if any(b in href for b in ("yellowpages", "google.com",
                                               "facebook.com", "instagram.com",
                                               "twitter.com", "linkedin.com")):
                        continue
                    if href.startswith("http"):
                        website = href
                        break

                if website:
                    continue   # has a site → not a lead

                yield Lead(
                    name=name,
                    country=country.code,
                    city=city,
                    category=term,
                    address=address or f"{city}, {country.name}",
                    phone=phone or "",
                    email=email,
                    website="",
                    instagram="",
                    facebook="",
                    linkedin="",
                    tiktok="",
                    source="yellowpages",
                )
            return   # success on this country; don't try the other URL variants
        except Exception as e:
            log.debug("Yellowpages %s: %s — %s", country.code, url, e)
