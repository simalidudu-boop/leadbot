"""
enrich/social_scraper.py — given a business name, search for its social
handles via Google (or via direct platform search if available).
"""
from __future__ import annotations

import re
from typing import Optional

from config import log
from http_client import get_text
from models import Lead


# Very simple DuckDuckGo HTML scrape fallback (no API key needed).
DDG_URL = "https://html.duckduckgo.com/html/"


def find_socials(lead: Lead) -> Lead:
    """Populate empty social fields by searching DDG."""
    if lead.has_any_social():
        return lead
    if not lead.name:
        return lead

    query = f'"{lead.name}" {lead.city}'.strip()
    try:
        r = get_text(DDG_URL, params={"q": query}, timeout=15)
        if not r:
            return lead
    except Exception as e:
        log.debug("DDG search failed for %s: %s", lead.name, e)
        return lead

    patterns = {
        "instagram": re.compile(r"instagram\.com/([\w.\-]+)", re.I),
        "facebook": re.compile(r"facebook\.com/([\w.\-]+)", re.I),
        "linkedin": re.compile(r"linkedin\.com/(?:in|company)/([\w.\-]+)", re.I),
        "tiktok": re.compile(r"tiktok\.com/@([\w.\-]+)", re.I),
    }
    for field, pattern in patterns.items():
        if getattr(lead, field, ""):
            continue
        m = pattern.search(r)
        if m:
            setattr(lead, field, m.group(0))
            log.debug("DDG found %s for %s: %s", field, lead.name, m.group(0))
    return lead
