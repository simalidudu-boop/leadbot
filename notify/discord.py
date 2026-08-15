"""
notify/discord.py — Discord webhook pings.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests

from config import log
from models import Lead


def _post(webhook: str, payload: dict) -> bool:
    try:
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code in (200, 204):
            return True
        log.warning("Discord webhook HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("Discord webhook failed: %s", e)
        return False


def _social_url(kind: str, handle: str) -> Optional[str]:
    """Normalize a handle into a full URL."""
    h = (handle or "").strip()
    if not h:
        return None
    if h.startswith("http"):
        return h
    h = h.lstrip("@")
    if kind == "instagram":
        return f"https://instagram.com/{h}"
    if kind == "facebook":
        return f"https://facebook.com/{h}"
    if kind == "linkedin":
        if "/" in h:
            return f"https://linkedin.com/{h}"
        return f"https://linkedin.com/in/{h}"
    if kind == "tiktok":
        return f"https://tiktok.com/@{h}"
    return None


def notify_no_email(lead: Lead, webhook: str) -> bool:
    """
    Ping Discord with a lead that has no email. Includes clickable
    social links so the human can reach out manually.
    """
    if not webhook:
        log.debug("Discord webhook not configured")
        return False

    # Build social link buttons as Discord "buttons" via a markdown
    # list (Discord doesn't support action buttons via webhooks unless
    # you have a bot — but the markdown links work great)
    social_lines = []
    for kind in ("instagram", "facebook", "linkedin", "tiktok"):
        handle = getattr(lead, kind, "") or ""
        url = _social_url(kind, handle)
        if url:
            display = handle if handle.startswith("http") else f"@{handle.lstrip('@')}"
            social_lines.append(f"• [{kind.title()}]({url}) → `{display}`")
    socials_text = "\n".join(social_lines) if social_lines else "_None found — manual lookup required_"

    maps_query = requests.utils.quote(f"{lead.name} {lead.city} {lead.country}")
    demo_section = (
        f"\n🎨 **Demo site (already built!):**\n{lead.demo_url}\n"
        if lead.demo_url else
        "\n_No demo built — click on the lead in Notion to trigger a build._\n"
    )

    embed = {
        "title": f"🚨 Lead needs manual outreach: {lead.name}",
        "description": (
            f"No email found. Please reach out via one of the socials below."
            f"{demo_section}"
        ),
        "color": 0xFF6B35,
        "fields": [
            {"name": "📍 Location",
             "value": f"{lead.city}, {lead.country}",
             "inline": True},
            {"name": "📞 Phone",
             "value": lead.phone or "_none_",
             "inline": True},
            {"name": "🏷️ Category",
             "value": lead.category or "_unknown_",
             "inline": True},
            {"name": "🔗 Socials (click to open)",
             "value": socials_text,
             "inline": False},
            {"name": "🗺️ Google Maps",
             "value": f"[Search for this business](https://www.google.com/maps/search/?api=1&query={maps_query})",
             "inline": True},
        ],
        "footer": {"text": f"lead_id: {lead.lead_id} • source: {lead.source or 'unknown'}"},
    }

    payload = {
        "username": "Lead Bot",
        "content": "📬 **Manual outreach needed**",
        "embeds": [embed],
    }
    return _post(webhook, payload)


def notify_error(message: str, webhook: str) -> bool:
    if not webhook:
        return False
    payload = {
        "username": "Lead Bot",
        "content": f"⚠️ **Error:** {message[:1500]}",
    }
    return _post(webhook, payload)
