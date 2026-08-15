"""
outreach/gmail_apps_script.py — send email via a Google Apps Script
deployed as a webhook.

Why this approach:
- No OAuth2 dance (no token refresh, no consent screens)
- Sends from your real Gmail account (full 500/day limit)
- Free (Gmail + Apps Script are both free)
- The webhook URL is a long random string; only the holder can call it

Setup (one time, 5 minutes):
1. Go to https://script.google.com
2. Click "+ New project"
3. Paste the code from gmail_apps_script_user_code.gs (provided separately)
4. Click "Deploy" → "New deployment"
5. Type: Web app
6. Execute as: Me
7. Who has access: Anyone (we'll use a secret URL for security)
8. Click "Deploy" → authorize → copy the Web App URL
9. Paste that URL as GMAIL_WEBHOOK_URL in your Railway env vars

The webhook URL looks like:
https://script.google.com/macros/s/AKfycbxxxxxxxxxxxxxxxxx/exec

That long middle section is the secret — anyone with the URL can
trigger the script. Don't share it.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from config import log
from models import Lead


# Apps Script web app POST endpoint accepts a JSON body
# Content-Type: application/json (or text/plain; they'll handle either)


def send_via_gmail(lead: Lead, *, subject: str, body: str,
                   from_email: str, from_name: str, webhook_url: str,
                   attachments: Optional[list[Path]] = None) -> bool:
    """
    Call the deployed Apps Script webhook to send an email from your
    Gmail. The script uses MailApp.sendEmail() which sends as your
    authenticated Google account.
    """
    if not webhook_url:
        return False

    payload = {
        "to": lead.email,
        "subject": subject,
        "body": body,
        "name": lead.name,
        "fromName": from_name,
    }

    if attachments:
        import base64
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
        r = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            # Apps Script redirects POST→GET sometimes; allow that
            allow_redirects=True,
        )
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                log.warning("Gmail webhook returned non-JSON: %s", r.text[:200])
                return False
            if data.get("status") == "sent":
                log.info("Gmail (via Apps Script): sent to %s", lead.email)
                return True
            log.warning("Gmail webhook returned: %s", data)
            return False
        log.warning("Gmail webhook HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("Gmail webhook request failed: %s", e)
        return False
