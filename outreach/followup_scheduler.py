"""
outreach/followup_scheduler.py — run the follow-up loop.

Reads the Leads sheet, finds leads needing follow-up, picks the right
template, sends it, updates the sheet.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from config import log
from outreach.email_providers import send_email
from models import Lead
from notion_crm import (
    add_lead, update_lead_status, get_leads, log_event, load_templates,
)
from state import load as load_state, increment_emails, record_bounce


# Follow-up cadence (days since last touch)
FOLLOWUP_PLAN = {
    "Contacted":      [3, 7, 14, 21],     # up to 4 follow-ups
    "No Response":    [3, 7],              # only 2 more
    "Interested":     [2, 5, 10],          # shorter, warmer
}


def _next_template_for(lead: Lead, status: str, templates: dict) -> tuple[str, str, str]:
    """
    Return (subject, body, template_key) appropriate for the lead's
    followup_count and status.
    """
    count = getattr(lead, "followup_count", 0) or 0
    plan = FOLLOWUP_PLAN.get(status, [])
    if count >= len(plan):
        return None, None, None

    if status == "Contacted":
        if count == 0:
            tkey = "email_followup_1"
        elif count == 1:
            tkey = "email_followup_2"
        else:
            tkey = "email_followup_final"
    elif status == "No Response":
        tkey = "email_followup_2" if count == 0 else "email_followup_final"
    elif status == "Interested":
        tkey = "email_followup_1" if count == 0 else "email_followup_2"
    else:
        tkey = "email_followup_final"

    tpl = templates.get(tkey) or {}
    return tpl.get("subject", ""), tpl.get("body", ""), tkey


def _due(lead_dict: dict, status: str) -> bool:
    plan = FOLLOWUP_PLAN.get(status, [])
    if not plan:
        return False
    count = int(lead_dict.get("followup_count") or 0)
    if count >= len(plan):
        return False
    last = lead_dict.get("last_touch_at") or lead_dict.get("first_sent_at") or ""
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    days = (datetime.utcnow() - last_dt).days
    target_day = plan[count]
    return days >= target_day


def run_followup_loop(settings) -> int:
    """
    Process all leads needing follow-up. Returns number of emails sent.
    """
    templates = load_templates()
    state = load_state()
    if state.get("emails_sent_today", 0) >= settings.daily_email_cap:
        log.info("Follow-up loop: daily cap reached (%d)",
                 settings.daily_email_cap)
        return 0

    sent = 0
    for status in ("Contacted", "No Response", "Interested"):
        leads = get_leads(statuses=[status])
        for lead_dict in leads:
            if state.get("emails_sent_today", 0) >= settings.daily_email_cap:
                log.info("Daily cap reached mid-loop; stopping")
                return sent
            if not _due(lead_dict, status):
                continue

            lead = _dict_to_lead(lead_dict)
            suggested_domain = f"{slugify(lead.name)}.{_tld(lead.country)}"

            subject_tpl, body_tpl, tkey = _next_template_for(lead, status, templates)
            if not subject_tpl:
                continue

            subject = _render(subject_tpl, lead, suggested_domain, settings)
            body = _render(body_tpl, lead, suggested_domain, settings)

            ok = send_email(lead, subject=subject, body=body, settings=settings)
            if ok:
                sent += 1
                state = increment_emails()
                update_lead_status(
                    lead.lead_id, status,
                    followup_count=int(lead_dict.get("followup_count") or 0) + 1,
                    last_touch_at=datetime.utcnow().isoformat(),
                )
                log_event("followup_sent", lead.lead_id,
                          f"{tkey} ({status})")
            else:
                log_event("followup_failed", lead.lead_id, tkey, "ERROR")
    return sent


def _dict_to_lead(d: dict) -> Lead:
    """Convert a Sheets row dict back into a Lead."""
    return Lead(
        name=d.get("name", ""),
        country=d.get("country", ""),
        city=d.get("city", ""),
        category=d.get("category", ""),
        address=d.get("address", ""),
        phone=d.get("phone", ""),
        email=d.get("email", ""),
        website=d.get("website", ""),
        instagram=d.get("instagram", ""),
        facebook=d.get("facebook", ""),
        linkedin=d.get("linkedin", ""),
        tiktok=d.get("tiktok", ""),
        source=d.get("source", ""),
        source_count=int(d.get("source_count") or 1),
        registry_hit=bool(d.get("registry_hit", False)),
        lead_id=d.get("lead_id", ""),
        followup_count=int(d.get("followup_count") or 0),
    )


def _render(tpl_str: str, lead: Lead, suggested_domain: str, settings) -> str:
    from outreach.templates import render_template
    return render_template(
        tpl_str, lead,
        suggested_domain=suggested_domain,
        sender_name=settings.from_name,
        sender_email=settings.from_email,
    )


def slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())[:20] or "yourbusiness"


def _tld(country: str) -> str:
    return {
        "ZA": "co.za", "ZW": "co.zw", "ZM": "co.zm",
        "BW": "co.bw", "KE": "co.ke",
    }.get(country, "com")
