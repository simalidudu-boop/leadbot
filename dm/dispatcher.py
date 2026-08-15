"""
dm/dispatcher.py — pick the best channel and send a DM.

Order: Facebook (free, official) → Instagram (free via instagrapi) →
       fall back to "no email" tab + Discord ping.
"""
from __future__ import annotations

import logging
from typing import Optional

from config import log
from outreach.templates import render_template
from models import Lead
from notion_crm import load_templates, add_no_email_lead, log_event

from . import facebook, instagram


def dm_lead(lead: Lead, settings, *,
            suggested_domain: str = "",
            sender_name: str = "",
            sender_email: str = "",
            demo_url: str = "") -> tuple[bool, str, str]:
    """
    Try to DM the lead. Returns (sent, channel, status).
    """
    templates = load_templates()
    body_tpl = (templates.get("dm_instagram") or {}).get("body", "")
    if not body_tpl:
        from config import DEFAULT_TEMPLATES
        body_tpl = DEFAULT_TEMPLATES["dm_instagram"]["body"]

    body = render_template(
        body_tpl, lead,
        suggested_domain=suggested_domain,
        sender_name=sender_name or settings.from_name,
        sender_email=sender_email or settings.from_email,
        extra={"demo_url": demo_url or lead.demo_url},
    )

    # 1. Facebook (preferred, free, official)
    if lead.facebook and settings.facebook_page_access_token:
        try:
            ok = facebook.send_dm(lead, body, settings.facebook_page_access_token)
            if ok:
                log_event("dm_sent", lead.lead_id, "facebook")
                return True, "facebook", "sent"
        except Exception as e:
            log.warning("Facebook DM failed for %s: %s", lead.name, e)

    # 2. Instagram (instagrapi, unofficial, free but can be flaky)
    if lead.instagram and settings.instagram_username and settings.instagram_password:
        try:
            ok = instagram.send_dm(lead, body,
                                   settings.instagram_username,
                                   settings.instagram_password)
            if ok:
                log_event("dm_sent", lead.lead_id, "instagram")
                return True, "instagram", "sent"
        except Exception as e:
            log.warning("Instagram DM failed for %s: %s", lead.name, e)

    # 3. No channel worked → log to no-email tab
    log_event("dm_no_channel", lead.lead_id,
              f"ig={bool(lead.instagram)} fb={bool(lead.facebook)}")
    return False, "none", "no_channel"
