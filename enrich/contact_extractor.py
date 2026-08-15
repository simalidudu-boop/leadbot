"""
enrich/contact_extractor.py — fetch a business's known online pages
(Google search snippet, Yelp page if any, etc.) and extract missing
contact info: email, phone, socials.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from config import log
from http_client import get_json, get_text
from models import Lead, is_valid_email, normalize_phone


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().\-]{7,}\d)")
SOCIAL_PATTERNS = {
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([\w.\-]+)", re.I),
    "facebook": re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([\w.\-]+)", re.I),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/([\w.\-]+)", re.I),
    "tiktok": re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@([\w.\-]+)", re.I),
}


def enrich_lead(lead: Lead, *, serpapi_key: str = "") -> Lead:
    """
    Try to fill in missing email/phone/socials. Cheap: 1-3 HTTP calls.
    """
    if lead.has_email() and lead.phone and lead.has_any_social():
        return lead   # already complete

    # 1. Try SerpAPI Google search if key available
    if serpapi_key and not lead.has_email():
        _try_google_search(lead, serpapi_key)

    # 2. Try the lead's known social pages if we have handles
    for field in ("instagram", "facebook", "linkedin", "tiktok"):
        handle = getattr(lead, field, "")
        if handle and not lead.has_email():
            url = _social_url(field, handle)
            if url:
                _scrape_public_social_page(lead, url, field)

    # 3. If we have a website (unlikely since we filtered, but possible
    #    from a registry), scrape it
    if lead.website and not lead.has_email():
        html = get_text(lead.website, timeout=15)
        if html:
            _extract_from_html(lead, html)

    # 4. Try guessing the domain & scraping it
    if not lead.has_email() and not lead.website:
        guessed = guess_domain(lead)
        if guessed:
            for scheme in ("https://", "http://"):
                html = get_text(scheme + guessed, timeout=10)
                if html:
                    _extract_from_html(lead, html)
                    lead.website = scheme + guessed
                    break

    return lead


def _try_google_search(lead: Lead, api_key: str) -> None:
    """Use SerpAPI free tier (100/month) to find the lead's contact info."""
    if not lead.name:
        return
    q = f'"{lead.name}" "{lead.city}" contact email'
    data = get_json(
        "https://serpapi.com/search.json",
        params={"q": q, "api_key": api_key, "num": 5},
    )
    if not data:
        return
    for r in (data.get("organic_results") or [])[:5]:
        snippet = r.get("snippet", "")
        m = EMAIL_RE.search(snippet)
        if m and is_valid_email(m.group(0)):
            lead.email = m.group(0)
            log.debug("SerpAPI found email for %s: %s", lead.name, lead.email)
            return


def _scrape_public_social_page(lead: Lead, url: str, kind: str) -> None:
    """Most social pages render via JS so this gets little, but worth trying."""
    html = get_text(url, timeout=10)
    if not html:
        return
    _extract_from_html(lead, html)


def _extract_from_html(lead: Lead, html: str) -> None:
    if not lead.email:
        m = EMAIL_RE.search(html)
        if m and is_valid_email(m.group(0)):
            lead.email = m.group(0)
    if not lead.phone:
        m = PHONE_RE.search(html)
        if m:
            lead.phone = normalize_phone(m.group(1))
    for field, pattern in SOCIAL_PATTERNS.items():
        if not getattr(lead, field, ""):
            m = pattern.search(html)
            if m:
                setattr(lead, field, m.group(0))


def _social_url(kind: str, handle: str) -> Optional[str]:
    handle = handle.strip().lstrip("@").rstrip("/")
    if not handle:
        return None
    if "http" in handle:
        return handle
    if kind == "instagram":
        return f"https://instagram.com/{handle}"
    if kind == "facebook":
        return f"https://facebook.com/{handle}"
    if kind == "linkedin":
        return f"https://linkedin.com/in/{handle}"
    if kind == "tiktok":
        return f"https://tiktok.com/@{handle}"
    return None


# ────────────────────────────────────────────────────────────────────
# Domain guessing
# ────────────────────────────────────────────────────────────────────
TLD_BY_COUNTRY = {
    "ZA": "co.za", "ZW": "co.zw", "ZM": "co.zm",
    "BW": "co.bw", "KE": "co.ke",
}


def guess_domain(lead: Lead) -> str:
    """Heuristically produce a likely domain for the business."""
    if not lead.name:
        return ""
    # Take first 2-3 significant words
    words = re.findall(r"[A-Za-z]+", lead.name.lower())
    words = [w for w in words if len(w) > 2 and w not in {
        "the", "and", "pty", "ltd", "limited", "company", "co", "inc",
        "llc", "group", "holdings", "trading", "enterprises", "services",
    }]
    if not words:
        return ""
    slug = "".join(words[:3])    # "acmeplumbing"
    tld = TLD_BY_COUNTRY.get(lead.country, "com")
    return f"{slug}.{tld}"
