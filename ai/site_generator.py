"""
ai/site_generator.py — orchestrates the full demo-site build:
1. Build prompt from lead
2. Call AI provider (with fallback)
3. Strip markdown fences
4. Save to local file in data/sites/
5. Return path + suggested filename
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import PROJECT_ROOT, log
from models import Lead

from . import provider
from .prompts import (
    SYSTEM_PROMPT,
    SITE_PROMPT,
    DIAL_CODES,
    COUNTRY_NAMES,
)


SITES_DIR = PROJECT_ROOT / "data" / "sites"
SITES_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "business"


def _socials_line(lead: Lead) -> str:
    parts = []
    if lead.instagram: parts.append(f"Instagram: {lead.instagram}")
    if lead.facebook: parts.append(f"Facebook: {lead.facebook}")
    if lead.linkedin: parts.append(f"LinkedIn: {lead.linkedin}")
    if lead.tiktok: parts.append(f"TikTok: {lead.tiktok}")
    return ", ".join(parts) or "none"


def _build_prompt(lead: Lead) -> str:
    return SITE_PROMPT.format(
        name=lead.name,
        category=lead.category or "small business",
        city=lead.city or COUNTRY_NAMES.get(lead.country, lead.country),
        country=COUNTRY_NAMES.get(lead.country, lead.country),
        address=lead.address or "",
        phone=lead.phone or "",
        email=lead.email or "",
        socials=_socials_line(lead),
    )


_HTML_FENCE = re.compile(r"^```(?:html)?\s*\n(.*?)\n```\s*$", re.S | re.I)


def _strip_fences(content: str) -> str:
    """Strip ```html ... ``` fences some models add despite instructions."""
    m = _HTML_FENCE.match(content.strip())
    if m:
        return m.group(1).strip()
    # If the response has leading 'html' and trailing '```', strip them.
    content = re.sub(r"^```html\s*\n?", "", content.strip(), flags=re.I)
    content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


def _ensure_html(html: str) -> str:
    if not html.lstrip().lower().startswith("<!doctype") and \
       not html.lstrip().lower().startswith("<html"):
        # Wrap a fragment in a basic shell
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Preview</title></head><body>"
            f"{html}</body></html>"
        )
    return html


def generate_demo_site(lead: Lead, settings, *, dry_run: bool = False
                       ) -> tuple[Optional[Path], str]:
    """
    Build the HTML for the lead's demo site.

    Returns (local_path, html_content).
    On failure, returns (None, "").
    """
    if dry_run:
        log.info("[dry-run] would generate site for %s", lead.name)
        return None, ""

    prompt = _build_prompt(lead)
    try:
        content = provider.generate(prompt, SYSTEM_PROMPT, settings)
    except Exception as e:
        log.error("AI generation failed for %s: %s", lead.name, e)
        return None, ""

    html = _ensure_html(_strip_fences(content))

    # Local file for the host step to deploy
    fname = f"{_slugify(lead.name)}-{lead.lead_id}.html"
    out_path = SITES_DIR / fname
    out_path.write_text(html, encoding="utf-8")
    log.info("Site generated for %s → %s (%d bytes)",
             lead.name, out_path, len(html))
    return out_path, html


def generate_screenshot_filename(lead: Lead) -> str:
    return f"{_slugify(lead.name)}-{lead.lead_id}.png"
