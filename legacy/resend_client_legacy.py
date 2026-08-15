"""
email/resend_client.py — send transactional email via Resend.

Resend free tier: 100 emails/day, 3,000/month.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from config import log
from models import Lead, is_valid_email
from .templates import render_template


RESEND_API = "https://api.resend.com/emails"


def send_email(
    lead: Lead,
    *,
    subject: str,
    body: str,
    settings,
    attachments: Optional[list[Path]] = None,
    html: bool = False,
) -> bool:
    """
    Send one email. Returns True on success. Respects DRY_RUN.
    """
    if not is_valid_email(lead.email):
        log.warning("send_email skipped — invalid email for %s: %r",
                    lead.name, lead.email)
        return False

    if settings.dry_run:
        log.info("[dry-run] would email %s <%s>: %s",
                 lead.name, lead.email, subject)
        log.info("[dry-run] body:\n%s", body)
        return True

    if not settings.resend_api_key:
        log.error("RESEND_API_KEY not set; cannot send email")
        return False

    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": f"{settings.from_name} <{settings.from_email}>",
        "to": [lead.email],
        "subject": subject,
    }
    if html:
        payload["html"] = body
    else:
        payload["text"] = body

    if attachments:
        atts = []
        for p in attachments:
            if not p or not p.exists():
                continue
            atts.append({
                "filename": p.name,
                "content": base64.b64encode(p.read_bytes()).decode("ascii"),
            })
        if atts:
            payload["attachments"] = atts

    try:
        r = requests.post(RESEND_API, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            log.info("Email sent to %s (%s): %s",
                     lead.email, lead.name, subject)
            return True
        log.error("Resend error %d: %s", r.status_code, r.text[:300])
        return False
    except requests.RequestException as e:
        log.error("Resend request failed: %s", e)
        return False
