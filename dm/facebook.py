"""
dm/facebook.py — send a DM via the Facebook Messenger Send API.

Free. Requires a Page access token with pages_messaging permission.
The bot must be a Page (or have a Page) to send on behalf of.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import log
from models import Lead


GRAPH_API = "https://graph.facebook.com/v19.0"


def send_dm(lead: Lead, body: str, page_access_token: str) -> bool:
    """
    Send a message to a user by PSID. NOTE: this requires the user to
    have already messaged your Page (24h customer window) OR for you
    to use the "message tags" feature with proper justification.
    For cold outreach this rarely works without sponsored messages.
    We attempt the call anyway, swallow errors, and report failure.
    """
    psid = _extract_psid_from_handle(lead.facebook)
    if not psid:
        log.debug("No PSID available for %s (handle: %s)",
                  lead.name, lead.facebook)
        return False

    url = f"{GRAPH_API}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"id": psid},
        "message": {"text": body[:2000]},
        "messaging_type": "MESSAGE_TAG",
        "tag": "ACCOUNT_UPDATE",
    }
    try:
        r = requests.post(url, params=params, json=payload, timeout=15)
        if r.status_code == 200:
            return True
        log.debug("Facebook DM HTTP %d: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        log.debug("Facebook DM request failed: %s", e)
        return False


def _extract_psid_from_handle(handle: str) -> Optional[str]:
    """
    Facebook Messenger requires the recipient's PSID, not their handle.
    We can't resolve handle → PSID without app-level lookups that need
    approval. So this returns None in practice — meaning the FB branch
    will silently fail and we'll fall through to IG or Discord.

    The infrastructure is here; you'd typically pair this with a contact
    form on your own site to capture PSIDs opt-in.
    """
    return None
