"""
models.py — typed Lead dataclass + helpers.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from config import is_chain, score_lead


def make_lead_id(phone: str, name: str, city: str) -> str:
    """Stable, dedupe-friendly ID."""
    raw = f"{(phone or '').strip()}|{(name or '').strip().lower()}|{(city or '').strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


_PHONE_CLEAN = re.compile(r"[^\d+]")


def normalize_phone(p: str | None) -> str:
    if not p:
        return ""
    return _PHONE_CLEAN.sub("", p)


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(e: str | None) -> bool:
    if not e:
        return False
    return bool(_EMAIL_RE.match(e.strip()))


@dataclass
class Lead:
    name: str
    country: str = ""
    city: str = ""
    category: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    instagram: str = ""
    facebook: str = ""
    linkedin: str = ""
    tiktok: str = ""
    source: str = ""
    source_count: int = 1
    registry_hit: bool = False

    # Computed / not from scrapers
    lead_id: str = ""
    lead_score: int = 0
    score_breakdown: dict = field(default_factory=dict)
    status: str = "New"
    demo_url: str = ""
    screenshot_url: str = ""
    first_sent_at: str = ""
    last_touch_at: str = ""
    followup_count: int = 0
    notes: str = ""

    def __post_init__(self):
        self.phone = normalize_phone(self.phone)
        if not self.lead_id:
            self.lead_id = make_lead_id(self.phone, self.name, self.city)
        if not self.lead_score:
            self.lead_score, self.score_breakdown = score_lead(asdict(self))

    def to_row(self) -> list[str]:
        """Return values in the order of LEAD_COLUMNS."""
        from config import LEAD_COLUMNS
        import json as _json
        d = asdict(self)
        d["score_breakdown"] = _json.dumps(self.score_breakdown)
        return [str(d.get(c, "") or "") for c in LEAD_COLUMNS]

    def has_email(self) -> bool:
        return is_valid_email(self.email)

    def has_website(self) -> bool:
        return bool(self.website and self.website.strip())

    def has_any_social(self) -> bool:
        return any([self.instagram, self.facebook, self.linkedin, self.tiktok])

    def is_chain(self) -> bool:
        return is_chain(self.name)

    def to_no_email_row(self) -> list[str]:
        """Row for the 'No Email' tab."""
        from config import NO_EMAIL_COLUMNS
        d = asdict(self)
        # Strip email-related & send-related fields, fill in no-email metadata
        d.pop("email", None)
        d.pop("status", None)
        d.pop("demo_url", None)
        d.pop("screenshot_url", None)
        d.pop("first_sent_at", None)
        d.pop("last_touch_at", None)
        d.pop("followup_count", None)
        d.pop("notes", None)
        d["discord_notified_at"] = ""
        d["dm_attempted_at"] = ""
        d["dm_status"] = ""
        return [str(d.get(c, "") or "") for c in NO_EMAIL_COLUMNS]
