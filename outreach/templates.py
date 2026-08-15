"""
email/templates.py — render Jinja2 templates for emails & DMs.
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

from jinja2 import Environment, BaseLoader, StrictUndefined

from config import log


JINJA = Environment(loader=BaseLoader(), undefined=StrictUndefined,
                    keep_trailing_newline=True)


def render_template(tpl: str, lead, *, suggested_domain: str = "",
                    sender_name: str = "", sender_email: str = "",
                    extra: Optional[dict] = None) -> str:
    """
    Render a template string with lead context. Unknown variables raise
    (StrictUndefined) so we catch typos early.
    """
    ctx = {
        "name": lead.name.split(" ")[0] if lead.name else "there",
        "business_name": lead.name,
        "city": lead.city,
        "country": lead.country,
        "category": lead.category or "your business",
        "phone": lead.phone,
        "email": lead.email,
        "demo_url": getattr(lead, "demo_url", ""),
        "screenshot_url": getattr(lead, "screenshot_url", ""),
        "suggested_domain": suggested_domain or f"{slug(lead.name)}.com",
        "sender_name": sender_name,
        "sender_email": sender_email,
        "followup_count": getattr(lead, "followup_count", 0),
    }
    if extra:
        ctx.update(extra)
    return JINJA.from_string(tpl).render(**ctx)


def slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())[:20] or "yourbusiness"
