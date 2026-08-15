"""
sheets.py — Google Sheets wrapper for the CRM.

Handles:
- Auto-creating the 5 required tabs
- Reading/writing leads
- Updating status columns
- Reading the Templates & Settings tabs
- Logging events
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import (
    LEAD_COLUMNS,
    NO_EMAIL_COLUMNS,
    PROJECT_ROOT,
    VALID_STATUSES,
    log,
)
from models import Lead

# Lazy-import gspread so --init works even if creds aren't set yet
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _HAS_GSPREAD = True
except ImportError:
    _HAS_GSPREAD = False


SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


TAB_LEADS = "Leads"
TAB_NO_EMAIL = "No Email"
TAB_TEMPLATES = "Templates"
TAB_LOGS = "Logs"
TAB_SETTINGS = "Settings"

ALL_TABS = [TAB_LEADS, TAB_NO_EMAIL, TAB_TEMPLATES, TAB_LOGS, TAB_SETTINGS]


# ────────────────────────────────────────────────────────────────────
# Auth
# ────────────────────────────────────────────────────────────────────
def _load_credentials() -> dict:
    """
    Load service-account JSON. Tries in order:
      1. GOOGLE_SHEETS_CREDENTIALS_B64 (base64-encoded JSON — best for CI)
      2. GOOGLE_SHEETS_CREDENTIALS (file path or raw JSON)
    Returns the parsed dict ready for gspread.
    """
    # 1. Base64 first (cleaner for cloud platforms)
    b64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS_B64", "")
    if b64:
        try:
            return json.loads(base64.b64decode(b64).decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Could not decode GOOGLE_SHEETS_CREDENTIALS_B64: {e}")

    # 2. Path or raw JSON
    raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    if not raw:
        raise RuntimeError(
            "Neither GOOGLE_SHEETS_CREDENTIALS_B64 nor "
            "GOOGLE_SHEETS_CREDENTIALS is set."
        )

    # Looks like a JSON object (starts with '{')
    if raw.lstrip().startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GOOGLE_SHEETS_CREDENTIALS is not valid JSON: {e}")

    # Otherwise treat as a file path
    path = Path(raw)
    if not path.exists():
        raise FileNotFoundError(f"Service account JSON not found at {path}")
    return json.loads(path.read_text())


def get_client():
    if not _HAS_GSPREAD:
        raise RuntimeError("gspread not installed. Run: pip install gspread google-auth")
    creds_dict = _load_credentials()
    creds = Credentials.from_service_account_info(creds_dict, scopes=SHEET_SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is empty.")
    return get_client().open_by_key(sheet_id)


# ────────────────────────────────────────────────────────────────────
# Bootstrap
# ────────────────────────────────────────────────────────────────────
def init_sheet() -> None:
    """
    Create the 5 required tabs and seed them with headers + default
    templates + default settings. Idempotent — safe to re-run.
    """
    log.info("Initializing Google Sheet...")
    sh = get_sheet()

    existing = {ws.title for ws in sh.worksheets()}

    for tab, headers in [
        (TAB_LEADS, LEAD_COLUMNS),
        (TAB_NO_EMAIL, NO_EMAIL_COLUMNS),
        (TAB_LOGS, ["timestamp", "level", "event", "lead_id", "detail"]),
    ]:
        if tab in existing:
            log.info("  ✓ %s already exists", tab)
            ws = sh.worksheet(tab)
            # Verify header row matches (warn if not)
            current = ws.row_values(1)
            if current != headers:
                log.warning(
                    "  ! %s headers don't match expected. Got: %s, Expected: %s",
                    tab, current, headers,
                )
        else:
            log.info("  + creating %s", tab)
            ws = sh.add_worksheet(title=tab, rows=1000, cols=max(len(headers), 5))
            ws.append_row(headers)

    # Templates tab
    if TAB_TEMPLATES in existing:
        log.info("  ✓ %s already exists", TAB_TEMPLATES)
    else:
        log.info("  + creating %s", TAB_TEMPLATES)
        ws = sh.add_worksheet(title=TAB_TEMPLATES, rows=100, cols=3)
        ws.append_row(["template_key", "subject", "body"])
        from config import DEFAULT_TEMPLATES
        for key, tpl in DEFAULT_TEMPLATES.items():
            ws.append_row([key, tpl.get("subject", ""), tpl["body"]])
        log.info("  seeded %d default templates", len(DEFAULT_TEMPLATES))

    # Settings tab
    if TAB_SETTINGS in existing:
        log.info("  ✓ %s already exists", TAB_SETTINGS)
    else:
        log.info("  + creating %s", TAB_SETTINGS)
        ws = sh.add_worksheet(title=TAB_SETTINGS, rows=50, cols=2)
        ws.append_row(["key", "value"])
        for k, v in [
            ("pause_all", "FALSE"),
            ("daily_email_cap_override", ""),
            ("per_country_caps", "ZA:25,ZW:15,ZM:15,BW:10,KE:20"),
            ("categories_blocklist", ""),
            ("categories_allowlist", ""),
            ("sender_name_override", ""),
            ("unsubscribe_footer", "If you'd rather I didn't email again, reply STOP."),
        ]:
            ws.append_row([k, v])

    log.info("Sheet initialization complete.")


# ────────────────────────────────────────────────────────────────────
# Templates
# ────────────────────────────────────────────────────────────────────
def load_templates() -> dict[str, dict[str, str]]:
    """
    Returns {template_key: {subject, body}}. Falls back to defaults if tab
    is empty or missing.
    """
    try:
        ws = get_sheet().worksheet(TAB_TEMPLATES)
    except Exception as e:
        log.warning("Couldn't read Templates tab: %s; using defaults", e)
        from config import DEFAULT_TEMPLATES
        return DEFAULT_TEMPLATES

    records = ws.get_all_records()
    if not records:
        from config import DEFAULT_TEMPLATES
        return DEFAULT_TEMPLATES

    out: dict[str, dict[str, str]] = {}
    for r in records:
        key = r.get("template_key")
        if not key:
            continue
        out[key] = {
            "subject": r.get("subject", ""),
            "body": r.get("body", ""),
        }
    return out


# ────────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────────
def load_settings() -> dict[str, str]:
    try:
        ws = get_sheet().worksheet(TAB_SETTINGS)
    except Exception as e:
        log.warning("Couldn't read Settings tab: %s", e)
        return {}

    return {r["key"]: r.get("value", "")
            for r in ws.get_all_records()
            if r.get("key")}


# ────────────────────────────────────────────────────────────────────
# Leads
# ────────────────────────────────────────────────────────────────────
def _ensure_leads_tab() -> Any:
    sh = get_sheet()
    try:
        return sh.worksheet(TAB_LEADS)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB_LEADS, rows=1000, cols=len(LEAD_COLUMNS))
        ws.append_row(LEAD_COLUMNS)
        return ws


def _build_lead_id_index(ws) -> dict[str, int]:
    """
    Build {lead_id: row_number} index. The lead_id column is the LAST
    column in LEAD_COLUMNS (index = len(LEAD_COLUMNS) = 23 → column W).
    """
    col_letter = _col_index_to_letter(len(LEAD_COLUMNS))   # 1-based → A
    col_values = ws.col_values(_col_letter_to_index(col_letter))
    out: dict[str, int] = {}
    for i, v in enumerate(col_values[1:], start=2):    # skip header
        if v:
            out[v] = i
    return out


def _col_index_to_letter(idx: int) -> str:
    """1-based index → A, B, ..., AA."""
    result = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def _col_letter_to_index(letter: str) -> int:
    """A → 1, B → 2, ..., AA → 27."""
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch.upper()) - 64)
    return result


def lead_exists(lead_id: str) -> bool:
    """Cheap existence check."""
    try:
        ws = _ensure_leads_tab()
        idx = _build_lead_id_index(ws)
        return lead_id in idx
    except Exception as e:
        log.warning("lead_exists check failed: %s", e)
        return False


def add_lead(lead: Lead) -> bool:
    """
    Append a new lead. Returns True if inserted, False if duplicate.
    """
    ws = _ensure_leads_tab()
    idx = _build_lead_id_index(ws)
    if lead.lead_id in idx:
        return False
    ws.append_row(lead.to_row(), value_input_option="USER_ENTERED")
    log_event("lead_added", lead.lead_id, f"{lead.name} ({lead.city}, {lead.country})")
    return True


def get_leads(
    statuses: Optional[list[str]] = None,
    country: Optional[str] = None,
    needs_followup: bool = False,
    max_age_hours: int = 168,
) -> list[dict[str, Any]]:
    """
    Read leads from the sheet as dicts.

    `needs_followup=True` returns leads whose status is in {Contacted,
    No Response, Interested} and whose last_touch_at is older than the
    follow-up cadence.

    `max_age_hours` controls how old a lead can be to be considered
    actionable for follow-up (default 7 days).
    """
    ws = _ensure_leads_tab()
    records = ws.get_all_records()
    out: list[dict[str, Any]] = []

    for r in records:
        if statuses and r.get("status") not in statuses:
            continue
        if country and r.get("country") != country:
            continue
        if needs_followup:
            from datetime import datetime, timedelta
            last = r.get("last_touch_at") or r.get("first_sent_at") or ""
            if not last:
                continue
            try:
                last_dt = datetime.fromisoformat(last)
            except Exception:
                continue
            if datetime.utcnow() - last_dt < timedelta(hours=24):
                continue
            if (datetime.utcnow() - last_dt).days > 14:
                continue
        out.append(r)
    return out


def update_lead_status(lead_id: str, status: str, **fields) -> bool:
    """
    Update a lead's status (and any other fields) by lead_id.
    """
    if status not in VALID_STATUSES and status != "Auto":
        log.warning("Status '%s' not in VALID_STATUSES, writing anyway", status)

    ws = _ensure_leads_tab()
    idx = _build_lead_id_index(ws)
    if lead_id not in idx:
        log.warning("update_lead_status: lead_id %s not found", lead_id)
        return False

    row = idx[lead_id]
    # Build a dict of column_index -> new value
    updates: dict[int, str] = {}

    # status
    status_col = _col_letter_to_index("O")
    updates[status_col] = status

    # last_touch_at
    updates[_col_letter_to_index("S")] = datetime.utcnow().isoformat()

    # arbitrary extra fields
    field_to_col = {
        "demo_url": "P",
        "screenshot_url": "Q",
        "first_sent_at": "R",
        "followup_count": "T",
        "notes": "U",
    }
    for k, col in field_to_col.items():
        if k in fields and fields[k] is not None:
            updates[_col_letter_to_index(col)] = str(fields[k])

    # Increment followup_count
    if "followup_count" not in fields:
        existing = ws.cell(row, _col_letter_to_index("T")).value or "0"
        try:
            updates[_col_letter_to_index("T")] = str(int(existing) + 1)
        except ValueError:
            updates[_col_letter_to_index("T")] = "1"

    for col_idx, val in updates.items():
        ws.update_cell(row, col_idx, val)

    log_event("status_updated", lead_id, f"→ {status}")
    return True


# ────────────────────────────────────────────────────────────────────
# No Email tab
# ────────────────────────────────────────────────────────────────────
def _ensure_no_email_tab() -> Any:
    sh = get_sheet()
    try:
        return sh.worksheet(TAB_NO_EMAIL)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB_NO_EMAIL, rows=1000, cols=len(NO_EMAIL_COLUMNS))
        ws.append_row(NO_EMAIL_COLUMNS)
        return ws


def add_no_email_lead(lead: Lead, discord_notified: bool = False) -> bool:
    ws = _ensure_no_email_tab()
    col_letter = _col_index_to_letter(len(NO_EMAIL_COLUMNS))
    col_values = ws.col_values(_col_letter_to_index(col_letter))
    existing_ids = {v for v in col_values[1:] if v}
    if lead.lead_id in existing_ids:
        return False

    row = lead.to_no_email_row()
    # Set discord_notified flag
    if discord_notified:
        # column is discord_notified_at, the 14th index (0-based 13)
        from config import NO_EMAIL_COLUMNS as C
        i = C.index("discord_notified_at")
        row[i] = datetime.utcnow().isoformat()
    ws.append_row(row, value_input_option="USER_ENTERED")
    log_event("no_email_added", lead.lead_id, f"{lead.name} ({lead.country})")
    return True


# ────────────────────────────────────────────────────────────────────
# Logs
# ────────────────────────────────────────────────────────────────────
def log_event(event: str, lead_id: str = "", detail: str = "", level: str = "INFO") -> None:
    """Append a row to the Logs tab. Never raises."""
    try:
        sh = get_sheet()
        try:
            ws = sh.worksheet(TAB_LOGS)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=TAB_LOGS, rows=1000, cols=5)
            ws.append_row(["timestamp", "level", "event", "lead_id", "detail"])
        ws.append_row([
            datetime.utcnow().isoformat(),
            level,
            event,
            lead_id,
            detail[:490],  # cell limit
        ])
    except Exception as e:
        log.warning("log_event to Sheets failed: %s", e)


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--init" in sys.argv:
        init_sheet()
    else:
        print("Usage: python -m leadbot.sheets --init")
        sys.exit(1)
