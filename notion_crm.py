"""
notion_crm.py — Notion as the CRM (replaces Google Sheets).

Why Notion:
- Free tier: no card required
- Generous limits for our use (we'll have <1k leads/month)
- Public API free with rate limits (3 req/s, easily handled)
- The user views leads in a Notion database — nicer UI than Sheets

Setup (one-time):
1. Create a Notion integration: https://www.notion.so/profile/integrations
2. Copy the "Internal Integration Secret" → NOTION_API_KEY
3. Create a database in Notion with the columns listed in LEAD_PROPERTIES
4. Share the database with your integration (click "..." → "Connections" → add)
5. Copy the database ID from the URL → NOTION_DATABASE_ID
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

from config import log
from models import Lead, is_valid_email


NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ────────────────────────────────────────────────────────────────────
# Notion property schema
# ────────────────────────────────────────────────────────────────────
LEAD_PROPERTIES = {
    "Name":                 {"type": "title"},
    "Country":              {"type": "select", "options": ["ZA", "ZW", "ZM", "BW", "KE"]},
    "City":                 {"type": "rich_text"},
    "Category":             {"type": "rich_text"},
    "Address":              {"type": "rich_text"},
    "Phone":                {"type": "phone_number"},
    "Email":                {"type": "email"},
    "Website":              {"type": "url"},
    "Instagram":            {"type": "url"},
    "Facebook":             {"type": "url"},
    "LinkedIn":             {"type": "url"},
    "TikTok":               {"type": "url"},
    "Source":               {"type": "rich_text"},
    "Source Count":         {"type": "number"},
    "Lead Score":           {"type": "number"},
    "Status": {
        "type": "select",
        "options": ["New", "Contacted", "No Response", "Interested",
                    "Bought", "Not Interested", "Bounced", "Paused"],
    },
    "Demo URL":             {"type": "url"},
    "Screenshot URL":       {"type": "rich_text"},
    "First Sent":           {"type": "date"},
    "Last Touch":           {"type": "date"},
    "Followup Count":       {"type": "number"},
    "Notes":                {"type": "rich_text"},
    "Lead ID":              {"type": "rich_text"},   # not "unique" — Notion has no SHA1 type
}

NO_EMAIL_PROPERTIES = {
    "Name":                 {"type": "title"},
    "Country":              {"type": "select", "options": ["ZA", "ZW", "ZM", "BW", "KE"]},
    "City":                 {"type": "rich_text"},
    "Category":             {"type": "rich_text"},
    "Address":              {"type": "rich_text"},
    "Phone":                {"type": "phone_number"},
    "Website":              {"type": "url"},
    "Instagram":            {"type": "url"},
    "Facebook":             {"type": "url"},
    "LinkedIn":             {"type": "url"},
    "TikTok":               {"type": "url"},
    "Source":               {"type": "rich_text"},
    "Lead Score":           {"type": "number"},
    "Discord Notified":     {"type": "date"},
    "DM Attempted":         {"type": "date"},
    "DM Status":            {"type": "rich_text"},
    "Lead ID":              {"type": "rich_text"},
}

TEMPLATES_PROPERTIES = {
    "Template Key": {"type": "title"},
    "Subject":      {"type": "rich_text"},
    "Body":         {"type": "rich_text"},
}

LOGS_PROPERTIES = {
    "Timestamp": {"type": "date"},
    "Level":     {"type": "select", "options": ["INFO", "WARNING", "ERROR"]},
    "Event":     {"type": "title"},
    "Lead ID":   {"type": "rich_text"},
    "Detail":    {"type": "rich_text"},
}

SETTINGS_PROPERTIES = {
    "Key":   {"type": "title"},
    "Value": {"type": "rich_text"},
}


# ────────────────────────────────────────────────────────────────────
# HTTP wrapper (Notion's API is finicky about rate limits)
# ────────────────────────────────────────────────────────────────────
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY', '')}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _db_id() -> str:
    v = os.getenv("NOTION_DATABASE_ID", "")
    if not v:
        raise RuntimeError("NOTION_DATABASE_ID is empty")
    # Users sometimes paste the full URL; extract the 32-char ID
    m = re.search(r"([a-f0-9]{32})", v.replace("-", ""))
    if m:
        return m.group(1)
    return v


def _request(method: str, path: str, **kwargs) -> Optional[dict]:
    url = f"{NOTION_API}{path}"
    for attempt in range(3):
        try:
            r = requests.request(method, url, headers=_headers(),
                                 timeout=30, **kwargs)
            if r.status_code == 429:
                # Rate-limited — wait and retry
                wait = int(r.headers.get("Retry-After", "1"))
                log.warning("Notion rate-limited, sleeping %ds", wait)
                time.sleep(wait)
                continue
            if r.status_code not in (200, 201):
                log.warning("Notion %s %s → %d: %s",
                            method, path, r.status_code, r.text[:200])
                return None
            return r.json()
        except requests.RequestException as e:
            log.warning("Notion request failed: %s", e)
            time.sleep(1)
    return None


# ────────────────────────────────────────────────────────────────────
# Bootstrap — create the databases if they don't exist
# ────────────────────────────────────────────────────────────────────
def init_crm() -> None:
    """
    Create the 5 databases (Leads, No Email, Templates, Logs, Settings)
    in a parent Notion page. The user must create the parent page
    manually (one click) and share it with the integration.
    """
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID", "")
    if not parent_page_id:
        raise RuntimeError(
            "NOTION_PARENT_PAGE_ID is empty. Create a Notion page, share "
            "it with your integration, and paste the page ID."
        )

    log.info("Initializing Notion CRM (idempotent)...")

    # Find existing databases in this workspace that the integration can see
    existing = _list_databases()
    existing_titles = {db.get("title", [{}])[0].get("plain_text", "")
                       for db in existing}

    desired = [
        ("Lead Bot — Leads",     LEAD_PROPERTIES),
        ("Lead Bot — No Email",  NO_EMAIL_PROPERTIES),
        ("Lead Bot — Templates", TEMPLATES_PROPERTIES),
        ("Lead Bot — Logs",      LOGS_PROPERTIES),
        ("Lead Bot — Settings",  SETTINGS_PROPERTIES),
    ]

    for title, props in desired:
        if title in existing_titles:
            log.info("  ✓ %s exists", title)
            continue
        log.info("  + creating %s", title)
        _create_database(title, props, parent_page_id)

    # Seed default templates if Templates is empty
    if "Lead Bot — Templates" in existing_titles:
        seed_templates_if_empty()

    log.info("Notion CRM initialization complete.")


def _list_databases() -> list[dict]:
    """Return all databases the integration can see."""
    out: list[dict] = []
    cursor = None
    while True:
        body = {"filter": {"property": "object", "value": "database"}}
        if cursor:
            body["start_cursor"] = cursor
        data = _request("POST", "/search", json=body)
        if not data:
            break
        out.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return out


def _create_database(title: str, properties: dict, parent_page_id: str) -> None:
    """Create a new database under a parent page."""
    body = {
        "parent": {"page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": _notion_property_schema(properties),
    }
    _request("POST", "/databases", json=body)


def _notion_property_schema(props: dict) -> dict:
    """Translate our {Name: {type: 'title'}} dict into Notion's API format."""
    out: dict[str, Any] = {}
    for name, spec in props.items():
        t = spec["type"]
        if t == "title":
            out[name] = {"title": {}}
        elif t == "rich_text":
            out[name] = {"rich_text": {}}
        elif t == "number":
            out[name] = {"number": {"format": "number"}}
        elif t == "date":
            out[name] = {"date": {}}
        elif t == "url":
            out[name] = {"url": {}}
        elif t == "email":
            out[name] = {"email": {}}
        elif t == "phone_number":
            out[name] = {"phone_number": {}}
        elif t == "select":
            opts = [{"name": o} for o in spec.get("options", [])]
            out[name] = {"select": {"options": opts}}
        else:
            out[name] = {"rich_text": {}}
    return out


def seed_templates_if_empty() -> None:
    """Add the default email/DM templates if the Templates database is empty."""
    from config import DEFAULT_TEMPLATES
    db_id = _find_database_id("Lead Bot — Templates")
    if not db_id:
        return
    existing = _query_all(db_id)
    if existing:
        return
    for key, tpl in DEFAULT_TEMPLATES.items():
        _request("POST", "/pages", json={
            "parent": {"database_id": db_id},
            "properties": {
                "Template Key": {"title": [{"text": {"content": key}}]},
                "Subject": {"rich_text": [{"text": {"content": tpl.get("subject", "")}}]},
                "Body": {"rich_text": [{"text": {"content": tpl["body"]}}]},
            },
        })


def _find_database_id(title: str) -> Optional[str]:
    for db in _list_databases():
        t = db.get("title", [{}])[0].get("plain_text", "")
        if t == title:
            return db["id"]
    return None


# ────────────────────────────────────────────────────────────────────
# Lead ↔ Notion conversion
# ────────────────────────────────────────────────────────────────────
def _lead_to_properties(lead: Lead) -> dict:
    """Convert a Lead dataclass into Notion's properties format."""
    return {
        "Name":           {"title":     [{"text": {"content": lead.name or "?"}}]},
        "Country":        {"select":    {"name": lead.country} if lead.country else None},
        "City":           {"rich_text": [{"text": {"content": lead.city or ""}}]},
        "Category":       {"rich_text": [{"text": {"content": lead.category or ""}}]},
        "Address":        {"rich_text": [{"text": {"content": lead.address or ""}}]},
        "Phone":          {"phone_number": lead.phone or None},
        "Email":          {"email":     lead.email or None},
        "Website":        {"url":       lead.website or None},
        "Instagram":      {"url":       lead.instagram or None},
        "Facebook":       {"url":       lead.facebook or None},
        "LinkedIn":       {"url":       lead.linkedin or None},
        "TikTok":         {"url":       lead.tiktok or None},
        "Source":         {"rich_text": [{"text": {"content": lead.source or ""}}]},
        "Source Count":   {"number":    lead.source_count},
        "Lead Score":     {"number":    lead.lead_score},
        "Status":         {"select":    {"name": lead.status or "New"}},
        "Demo URL":       {"url":       lead.demo_url or None},
        "Screenshot URL": {"rich_text": [{"text": {"content": lead.screenshot_url or ""}}]},
        "First Sent":     {"date":      {"start": lead.first_sent_at} if lead.first_sent_at else None},
        "Last Touch":     {"date":      {"start": lead.last_touch_at} if lead.last_touch_at else None},
        "Followup Count": {"number":    lead.followup_count},
        "Notes":          {"rich_text": [{"text": {"content": lead.notes or ""}}]},
        "Lead ID":        {"rich_text": [{"text": {"content": lead.lead_id}}]},
    }


def _properties_to_lead(props: dict) -> Lead:
    """Convert Notion properties dict back into a Lead."""
    def txt(name: str) -> str:
        v = props.get(name, {}).get("rich_text", [])
        return v[0]["text"]["content"] if v else ""

    def num(name: str, default=0) -> int:
        v = props.get(name, {}).get("number")
        return v if isinstance(v, (int, float)) else default

    def sel(name: str) -> str:
        v = props.get(name, {}).get("select")
        return v["name"] if v else ""

    def title(name: str) -> str:
        v = props.get(name, {}).get("title", [])
        return v[0]["text"]["content"] if v else ""

    def url(name: str) -> str:
        return props.get(name, {}).get("url") or ""

    def date(name: str) -> str:
        v = props.get(name, {}).get("date")
        return v["start"] if v else ""

    return Lead(
        name=title("Name"),
        country=sel("Country"),
        city=txt("City"),
        category=txt("Category"),
        address=txt("Address"),
        phone=props.get("Phone", {}).get("phone_number") or "",
        email=props.get("Email", {}).get("email") or "",
        website=url("Website"),
        instagram=url("Instagram"),
        facebook=url("Facebook"),
        linkedin=url("LinkedIn"),
        tiktok=url("TikTok"),
        source=txt("Source"),
        source_count=num("Source Count", 1),
        lead_score=num("Lead Score", 0),
        status=sel("Status") or "New",
        demo_url=url("Demo URL"),
        screenshot_url=txt("Screenshot URL"),
        first_sent_at=date("First Sent"),
        last_touch_at=date("Last Touch"),
        followup_count=num("Followup Count", 0),
        notes=txt("Notes"),
        lead_id=txt("Lead ID"),
    )


# ────────────────────────────────────────────────────────────────────
# Query helpers
# ────────────────────────────────────────────────────────────────────
def _query_all(database_id: str, filter_: Optional[dict] = None) -> list[dict]:
    """Return all rows (pages) in a database, with pagination."""
    out: list[dict] = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if filter_:
            body["filter"] = filter_
        if cursor:
            body["start_cursor"] = cursor
        data = _request("POST", f"/databases/{database_id}/query", json=body)
        if not data:
            break
        out.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return out


def _find_page_by_lead_id(database_id: str, lead_id: str) -> Optional[dict]:
    pages = _query_all(database_id, filter_={
        "property": "Lead ID",
        "rich_text": {"equals": lead_id},
    })
    return pages[0] if pages else None


# ────────────────────────────────────────────────────────────────────
# Public API — mirrors the sheets.py interface
# ────────────────────────────────────────────────────────────────────
def lead_exists(lead_id: str) -> bool:
    db_id = _find_database_id("Lead Bot — Leads")
    if not db_id:
        return False
    return _find_page_by_lead_id(db_id, lead_id) is not None


def add_lead(lead: Lead) -> bool:
    db_id = _find_database_id("Lead Bot — Leads")
    if not db_id:
        log.error("Leads database not found in Notion")
        return False
    if _find_page_by_lead_id(db_id, lead.lead_id):
        return False
    _request("POST", "/pages", json={
        "parent": {"database_id": db_id},
        "properties": _lead_to_properties(lead),
    })
    log_event("lead_added", lead.lead_id, f"{lead.name} ({lead.country})")
    return True


def get_leads(statuses: Optional[list[str]] = None,
              needs_followup: bool = False) -> list[dict]:
    """Return leads matching the given statuses, as dicts."""
    db_id = _find_database_id("Lead Bot — Leads")
    if not db_id:
        return []
    filter_: dict = {}
    if statuses:
        filter_ = {
            "and": [{"property": "Status", "select": {"equals": s}}
                    for s in statuses],
        }
    pages = _query_all(db_id, filter_=filter_ or None)
    out: list[dict] = []
    for p in pages:
        props = p.get("properties", {})
        lead = _properties_to_lead(props)
        d = {
            "name": lead.name, "country": lead.country, "city": lead.city,
            "category": lead.category, "address": lead.address,
            "phone": lead.phone, "email": lead.email, "website": lead.website,
            "instagram": lead.instagram, "facebook": lead.facebook,
            "linkedin": lead.linkedin, "tiktok": lead.tiktok,
            "source": lead.source, "source_count": lead.source_count,
            "lead_score": lead.lead_score, "status": lead.status,
            "demo_url": lead.demo_url, "screenshot_url": lead.screenshot_url,
            "first_sent_at": lead.first_sent_at,
            "last_touch_at": lead.last_touch_at,
            "followup_count": lead.followup_count, "notes": lead.notes,
            "lead_id": lead.lead_id, "_page_id": p["id"],
        }
        out.append(d)
    return out


def update_lead_status(lead_id: str, status: str, **fields) -> bool:
    db_id = _find_database_id("Lead Bot — Leads")
    if not db_id:
        return False
    page = _find_page_by_lead_id(db_id, lead_id)
    if not page:
        log.warning("update_lead_status: lead_id %s not found", lead_id)
        return False

    properties: dict = {"Status": {"select": {"name": status}}}
    if "last_touch_at" not in fields:
        properties["Last Touch"] = {"date": {"start": datetime.utcnow().isoformat()}}
    for k, v in fields.items():
        if k == "last_touch_at" and v:
            properties["Last Touch"] = {"date": {"start": v}}
        elif k == "first_sent_at" and v:
            properties["First Sent"] = {"date": {"start": v}}
        elif k == "demo_url":
            properties["Demo URL"] = {"url": v or None}
        elif k == "screenshot_url":
            properties["Screenshot URL"] = {"rich_text": [{"text": {"content": v or ""}}]}
        elif k == "followup_count" and v is not None:
            properties["Followup Count"] = {"number": v}
        elif k == "notes":
            properties["Notes"] = {"rich_text": [{"text": {"content": v or ""}}]}

    _request("PATCH", f"/pages/{page['id']}", json={"properties": properties})
    log_event("status_updated", lead_id, f"→ {status}")
    return True


def add_no_email_lead(lead: Lead, discord_notified: bool = False) -> bool:
    db_id = _find_database_id("Lead Bot — No Email")
    if not db_id:
        return False
    if _find_page_by_lead_id(db_id, lead.lead_id):
        return False
    properties = {
        "Name":          {"title": [{"text": {"content": lead.name or "?"}}]},
        "Country":       {"select": {"name": lead.country} if lead.country else None},
        "City":          {"rich_text": [{"text": {"content": lead.city or ""}}]},
        "Category":      {"rich_text": [{"text": {"content": lead.category or ""}}]},
        "Address":       {"rich_text": [{"text": {"content": lead.address or ""}}]},
        "Phone":         {"phone_number": lead.phone or None},
        "Website":       {"url": lead.website or None},
        "Instagram":     {"url": lead.instagram or None},
        "Facebook":      {"url": lead.facebook or None},
        "LinkedIn":      {"url": lead.linkedin or None},
        "TikTok":        {"url": lead.tiktok or None},
        "Source":        {"rich_text": [{"text": {"content": lead.source or ""}}]},
        "Lead Score":    {"number": lead.lead_score},
        "DM Status":     {"rich_text": [{"text": {"content": ""}}]},
        "Lead ID":       {"rich_text": [{"text": {"content": lead.lead_id}}]},
    }
    if discord_notified:
        properties["Discord Notified"] = {"date": {"start": datetime.utcnow().isoformat()}}
    _request("POST", "/pages", json={
        "parent": {"database_id": db_id},
        "properties": properties,
    })
    log_event("no_email_added", lead.lead_id, f"{lead.name} ({lead.country})")
    return True


def update_no_email_dm(lead_id: str, dm_status: str) -> None:
    db_id = _find_database_id("Lead Bot — No Email")
    if not db_id:
        return
    page = _find_page_by_lead_id(db_id, lead_id)
    if not page:
        return
    _request("PATCH", f"/pages/{page['id']}", json={
        "properties": {
            "DM Attempted": {"date": {"start": datetime.utcnow().isoformat()}},
            "DM Status":    {"rich_text": [{"text": {"content": dm_status}}]},
        }
    })


def load_templates() -> dict[str, dict[str, str]]:
    db_id = _find_database_id("Lead Bot — Templates")
    if not db_id:
        from config import DEFAULT_TEMPLATES
        return DEFAULT_TEMPLATES
    pages = _query_all(db_id)
    if not pages:
        from config import DEFAULT_TEMPLATES
        return DEFAULT_TEMPLATES

    out: dict[str, dict[str, str]] = {}
    for p in pages:
        props = p.get("properties", {})
        key = (props.get("Template Key", {}).get("title") or [{}])[0]\
            .get("text", {}).get("content", "")
        if not key:
            continue
        subj = (props.get("Subject", {}).get("rich_text") or [{}])
        body = (props.get("Body", {}).get("rich_text") or [{}])
        out[key] = {
            "subject": subj[0].get("text", {}).get("content", "") if subj else "",
            "body": body[0].get("text", {}).get("content", "") if body else "",
        }
    return out


def load_settings() -> dict[str, str]:
    db_id = _find_database_id("Lead Bot — Settings")
    if not db_id:
        return {}
    out: dict[str, str] = {}
    for p in _query_all(db_id):
        props = p.get("properties", {})
        key = (props.get("Key", {}).get("title") or [{}])[0]\
            .get("text", {}).get("content", "")
        if not key:
            continue
        val = (props.get("Value", {}).get("rich_text") or [{}])
        out[key] = val[0].get("text", {}).get("content", "") if val else ""
    return out


def log_event(event: str, lead_id: str = "", detail: str = "",
              level: str = "INFO") -> None:
    """Append a row to the Logs database."""
    try:
        db_id = _find_database_id("Lead Bot — Logs")
        if not db_id:
            return
        # Truncate detail to Notion's 2000-char limit
        detail = (detail or "")[:1900]
        _request("POST", "/pages", json={
            "parent": {"database_id": db_id},
            "properties": {
                "Timestamp": {"date": {"start": datetime.utcnow().isoformat()}},
                "Level":     {"select": {"name": level}},
                "Event":     {"title": [{"text": {"content": event[:200]}}]},
                "Lead ID":   {"rich_text": [{"text": {"content": lead_id or ""}}]},
                "Detail":    {"rich_text": [{"text": {"content": detail}}]},
            },
        })
    except Exception as e:
        log.warning("log_event to Notion failed: %s", e)
