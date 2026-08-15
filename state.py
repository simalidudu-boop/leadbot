"""
state.py — persistent on-disk state for the bot.

Holds small per-run data that doesn't belong in Sheets:
- daily counters (to enforce caps)
- bounced-domain list
- per-AI-provider daily usage
- last-run timestamp
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from threading import Lock
from typing import Any

from config import PROJECT_ROOT, log

STATE_DIR = PROJECT_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "lead_state.json"
_lock = Lock()


def _default_state() -> dict[str, Any]:
    return {
        "date": str(date.today()),
        "emails_sent_today": 0,
        "dms_sent_today": 0,
        "bounced_domains": {},          # domain -> count
        "paused_domains": set(),        # auto-paused after 3 bounces
        "ai_usage": {                   # provider -> neurons/credits used
            "cloudflare": 0,
            "mistral": 0,
            "cohere": 0,
            "groq": 0,
        },
        "last_run_at": None,
        "warmup_started_at": None,      # for 14-day ramp
        "leads_processed_total": 0,
    }


def load() -> dict[str, Any]:
    with _lock:
        if not STATE_FILE.exists():
            return _default_state()
        try:
            data = json.loads(STATE_FILE.read_text())
        except Exception as e:
            log.warning("Corrupt state file, resetting: %s", e)
            return _default_state()

        # Reset daily counters on a new day
        if data.get("date") != str(date.today()):
            data["date"] = str(date.today())
            data["emails_sent_today"] = 0
            data["dms_sent_today"] = 0
            data["ai_usage"] = _default_state()["ai_usage"]
        # Convert sets back (JSON loses them)
        if isinstance(data.get("paused_domains"), list):
            data["paused_domains"] = set(data["paused_domains"])
        return data


def save(state: dict[str, Any]) -> None:
    with _lock:
        out = {**state}
        if isinstance(out.get("paused_domains"), set):
            out["paused_domains"] = sorted(out["paused_domains"])
        STATE_FILE.write_text(json.dumps(out, indent=2, default=str))


def update(**changes) -> dict[str, Any]:
    state = load()
    state.update(changes)
    state["last_run_at"] = datetime.utcnow().isoformat()
    save(state)
    return state


def increment_emails(n: int = 1) -> dict[str, Any]:
    state = load()
    state["emails_sent_today"] = state.get("emails_sent_today", 0) + n
    state["leads_processed_total"] = state.get("leads_processed_total", 0) + n
    state["last_run_at"] = datetime.utcnow().isoformat()
    save(state)
    return state


def record_bounce(email: str) -> dict[str, Any]:
    state = load()
    domain = email.split("@", 1)[-1].lower() if "@" in email else email
    b = state.get("bounced_domains", {})
    b[domain] = b.get(domain, 0) + 1
    state["bounced_domains"] = b
    if b[domain] >= 3:
        paused = state.get("paused_domains", set())
        if isinstance(paused, list):
            paused = set(paused)
        paused.add(domain)
        state["paused_domains"] = paused
        log.warning("Auto-paused domain after 3 bounces: %s", domain)
    state["last_run_at"] = datetime.utcnow().isoformat()
    save(state)
    return state
