"""
dm/instagram.py — send a DM via the unofficial instagrapi library.

Free, no Meta approval needed, but Instagram aggressively throttles new
accounts. Use a warmed-up business account.
"""
from __future__ import annotations

import logging
from typing import Optional

from config import log
from models import Lead


def send_dm(lead: Lead, body: str, username: str, password: str) -> bool:
    """
    Send a DM to the lead's Instagram handle.
    """
    handle = _clean_handle(lead.instagram)
    if not handle:
        return False
    try:
        from instagrapi import Client
        cl = Client()
        cl.login(username, password)
        user_id = cl.user_id_from_username(handle)
        cl.direct_send(body[:1000], [user_id])
        log.info("Instagram DM sent to @%s", handle)
        return True
    except Exception as e:
        log.warning("Instagram DM to @%s failed: %s", handle, e)
        return False


def _clean_handle(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    for prefix in ("https://instagram.com/", "http://instagram.com/",
                   "instagram.com/", "@"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip("/")
