"""
outreach/email_providers.py — multi-provider email sending with fallback.

Order: Brevo (300/day free) → Resend (100/day free) → MailerSend (low-volume free)

All three require NO credit card. All three have free tiers.

API docs:
- Brevo: https://developers.brevo.com/reference/sendtransacemail
- Resend: https://resend.com/docs/api-reference/emails/send-email
- MailerSend: https://developers.mailersend.com/api/v1/email.html
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from config import log
from models import Lead, is_valid_email
from .gmail_apps_script import send_via_gmail as _send_via_gmail


# ────────────────────────────────────────────────────────────────────
# Brevo (primary)
# ────────────────────────────────────────────────────────────────────
def send_brevo(lead: Lead, *, subject: str, body: str,
               from_email: str, from_name: str, api_key: str,
               attachments: Optional[list[Path]] = None) -> bool:
    """300 emails/day free, no card. https://www.brevo.com"""
    if not api_key:
        return False
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": lead.email, "name": lead.name}],
        "subject": subject,
        "textContent": body,
    }
    if attachments:
        atts = []
        for p in attachments:
            if not p or not p.exists():
                continue
            atts.append({
                "content": base64.b64encode(p.read_bytes()).decode("ascii"),
                "name": p.name,
            })
        if atts:
            payload["attachment"] = atts
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201, 202):
            log.info("Brevo: sent to %s", lead.email)
            return True
        log.warning("Brevo HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("Brevo request failed: %s", e)
        return False


# ────────────────────────────────────────────────────────────────────
# Resend (fallback 1)
# ────────────────────────────────────────────────────────────────────
def send_resend(lead: Lead, *, subject: str, body: str,
                from_email: str, from_name: str, api_key: str,
                attachments: Optional[list[Path]] = None) -> bool:
    """100 emails/day free, no card. https://resend.com"""
    if not api_key:
        return False
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": [lead.email],
        "subject": subject,
        "text": body,
    }
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
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            log.info("Resend: sent to %s", lead.email)
            return True
        log.warning("Resend HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("Resend request failed: %s", e)
        return False


# ────────────────────────────────────────────────────────────────────
# MailerSend (fallback 2)
# ────────────────────────────────────────────────────────────────────
def send_mailersend(lead: Lead, *, subject: str, body: str,
                    from_email: str, from_name: str, api_key: str,
                    attachments: Optional[list[Path]] = None) -> bool:
    """Low-volume free tier, no card. https://www.mailersend.com"""
    if not api_key:
        return False
    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": {"email": from_email, "name": from_name},
        "to": [{"email": lead.email, "name": lead.name}],
        "subject": subject,
        "text": body,
    }
    if attachments:
        atts = []
        for p in attachments:
            if not p or not p.exists():
                continue
            atts.append({
                "content": base64.b64encode(p.read_bytes()).decode("ascii"),
                "filename": p.name,
            })
        if atts:
            payload["attachments"] = atts
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201, 202):
            log.info("MailerSend: sent to %s", lead.email)
            return True
        log.warning("MailerSend HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("MailerSend request failed: %s", e)
        return False


# ────────────────────────────────────────────────────────────────────
# Fallback chain
# ────────────────────────────────────────────────────────────────────
def send_email(lead: Lead, *, subject: str, body: str, settings,
               attachments: Optional[list[Path]] = None,
               html: bool = False) -> bool:
    """
    Try each provider in order. Returns True on first success.

    If settings.dry_run is True, just logs and returns True.
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

    chain = [
        ("Brevo", settings.brevo_api_key,
         lambda: send_brevo(lead, subject=subject, body=body,
                            from_email=settings.from_email,
                            from_name=settings.from_name,
                            api_key=settings.brevo_api_key,
                            attachments=attachments)),
        ("Resend", settings.resend_api_key,
         lambda: send_resend(lead, subject=subject, body=body,
                             from_email=settings.from_email,
                             from_name=settings.from_name,
                             api_key=settings.resend_api_key,
                             attachments=attachments)),
        ("MailerSend", settings.mailersend_api_key,
         lambda: send_mailersend(lead, subject=subject, body=body,
                                 from_email=settings.from_email,
                                 from_name=settings.from_name,
                                 api_key=settings.mailersend_api_key,
                                 attachments=attachments)),
    ]

    last_err = None
    for name, key, fn in chain:
        if not key:
            log.debug("Email provider %s not configured, skipping", name)
            continue
        try:
            ok = fn()
            if ok:
                return True
        except Exception as e:
            log.warning("Provider %s raised: %s", name, e)
            last_err = e

    log.error("All email providers failed for %s (last err: %s)",
              lead.name, last_err)
    return False
