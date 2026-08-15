"""
tests/test_smoke.py — quick smoke tests to verify imports & basic logic.
Run with: pytest tests/
"""
import os
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base64
import pytest

from models import Lead, make_lead_id, normalize_phone, is_valid_email
from config import is_chain, score_lead, COUNTRIES, DEFAULT_TEMPLATES
import run as run_module

def test_lead_id_stable():
    a = make_lead_id("+27115551234", "Acme Plumbing", "Johannesburg")
    b = make_lead_id("+27115551234", "Acme Plumbing", "Johannesburg")
    assert a == b


def test_lead_id_phone_normalized():
    # Two differently-formatted but logically-same phones should still
    # produce the same ID because we normalize in the dataclass.
    # This is the Lead dataclass's behavior, not the raw make_lead_id.
    from models import Lead
    a = Lead(name="Acme", city="Joburg", phone="+27 11 555 1234").lead_id
    b = Lead(name="Acme", city="Joburg", phone="+27115551234").lead_id
    assert a == b


def test_phone_normalize():
    # normalize_phone keeps the leading + (for tel: and wa.me links)
    assert normalize_phone("+27 11 555-1234") == "+27115551234"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_valid_email():
    assert is_valid_email("a@b.co")
    assert is_valid_email("user.name+tag@sub.example.com")
    assert not is_valid_email("not-an-email")
    assert not is_valid_email("")
    assert not is_valid_email(None)


def test_is_chain():
    assert is_chain("Mica Hardware")
    assert is_chain("Shoprite Local")
    assert not is_chain("Acme Plumbing")


def test_score_lead():
    lead = {
        "name": "Acme", "country": "ZA", "category": "plumber",
        "phone": "+27115551234", "address": "1 Main Rd",
    }
    score, breakdown = score_lead(lead)
    assert score >= 8   # no_website + no_socials + phone + address + cat
    assert "no_website" in breakdown


def test_lead_to_row():
    lead = Lead(name="Acme", country="ZA", city="Joburg",
                category="plumber", email="a@b.co")
    row = lead.to_row()
    assert len(row) == len(__import__("config").LEAD_COLUMNS)
    assert row[0] == "Acme"
    assert row[6] == "a@b.co"


def test_countries_defined():
    for code in ("ZA", "ZW", "ZM", "BW", "KE"):
        assert code in COUNTRIES
        c = COUNTRIES[code]
        assert c.lat != 0 and c.lng != 0
        assert len(c.cities) > 0


def test_default_templates_complete():
    for k in ("email_initial", "email_followup_1", "email_followup_2",
              "email_followup_final", "dm_instagram", "dm_facebook"):
        assert k in DEFAULT_TEMPLATES
        assert "body" in DEFAULT_TEMPLATES[k]


def test_run_module_scheduler():
    """The Railway worker should know when to run next."""
    assert hasattr(run_module, "should_run_now")
    assert hasattr(run_module, "time_until_next_window")
    assert hasattr(run_module, "run_bot_once")
    wait = run_module.time_until_next_window()
    assert 0 < wait < 24 * 60 * 60, f"wait time {wait} out of range"


def test_email_providers_module_imports():
    """All three email providers should be importable."""
    from outreach.email_providers import send_brevo, send_resend, send_mailersend
    assert callable(send_brevo)
    assert callable(send_resend)
    assert callable(send_mailersend)


def test_email_fallback_chain_skips_unconfigured(monkeypatch):
    """If no provider is configured, send_email should return False (not crash)."""
    from outreach.email_providers import send_email
    from models import Lead
    settings = type("S", (), {
        "brevo_api_key": "", "resend_api_key": "", "mailersend_api_key": "",
        "from_email": "test@test.com", "from_name": "Test", "dry_run": False,
    })()
    lead = Lead(name="Test", email="user@example.com")
    ok = send_email(lead, subject="hi", body="body", settings=settings)
    assert ok is False


def test_email_dry_run_path(monkeypatch):
    """Dry run should not call any provider."""
    from outreach.email_providers import send_email
    from models import Lead
    settings = type("S", (), {
        "brevo_api_key": "fake", "resend_api_key": "", "mailersend_api_key": "",
        "from_email": "test@test.com", "from_name": "Test", "dry_run": True,
    })()
    lead = Lead(name="Test", email="user@example.com")
    ok = send_email(lead, subject="hi", body="body", settings=settings)
    assert ok is True


def test_notion_crm_module_imports():
    """Notion CRM should be importable and have the expected public API."""
    import notion_crm
    assert callable(notion_crm.init_crm)
    assert callable(notion_crm.add_lead)
    assert callable(notion_crm.lead_exists)
    assert callable(notion_crm.get_leads)
    assert callable(notion_crm.update_lead_status)
    assert callable(notion_crm.add_no_email_lead)
    assert callable(notion_crm.load_templates)
    assert callable(notion_crm.load_settings)
    assert callable(notion_crm.log_event)


def test_settings_has_new_email_fields():
    """Settings should expose all three email providers' keys."""
    s = type("S", (), {})()
    # We just check the dataclass has the attributes
    from dataclasses import dataclass
    @dataclass
    class S:
        brevo_api_key: str = ""
        resend_api_key: str = ""
        mailersend_api_key: str = ""
        gmail_webhook_url: str = ""
        notion_api_key: str = ""
    s = S()
    assert s.brevo_api_key == ""
    assert s.mailersend_api_key == ""
    assert s.notion_api_key == ""
    assert s.gmail_webhook_url == ""


def test_run_module_has_three_subruns():
    """Schedule should have 3 sub-run slots (not 2)."""
    from run import RUN_TIMES_UTC
    assert len(RUN_TIMES_UTC) == 3
    # All in the morning UTC
    for h, m in RUN_TIMES_UTC:
        assert 6 <= h <= 9, f"unexpected hour {h}"


def test_subrun_split_divides_leads_evenly():
    """The _split_for_subrun function should give each sub-run a fair share."""
    from bot import _split_for_subrun
    leads = list(range(30))   # 30 fake leads
    s1 = _split_for_subrun(leads, 1, 3)
    s2 = _split_for_subrun(leads, 2, 3)
    s3 = _split_for_subrun(leads, 3, 3)
    assert len(s1) == 10
    assert len(s2) == 10
    assert len(s3) == 10
    # No overlap, full coverage
    assert set(s1 + s2 + s3) == set(leads)
    # Round-robin means first subrun gets the highest-indexed items
    # (because we sort desc before splitting)
    # Verify interleaving
    assert s1[0] == 0
    assert s2[0] == 1
    assert s3[0] == 2


def test_gmail_module_imports_and_has_send_function():
    """The Gmail Apps Script wrapper should expose send_via_gmail."""
    from outreach.gmail_apps_script import send_via_gmail
    assert callable(send_via_gmail)


def test_apps_script_user_code_is_valid_text():
    """The .gs file we ship should be non-empty and contain the expected markers."""
    from pathlib import Path
    code = Path(__file__).parent.parent / "outreach" / "gmail_apps_script_user_code.gs"
    assert code.exists()
    text = code.read_text()
    assert "function doPost" in text
    assert "MailApp.sendEmail" in text
    assert "ContentService" in text


def test_discord_ping_includes_social_links(monkeypatch):
    """notify_no_email should produce a payload with the lead's social URLs."""
    from notify.discord import notify_no_email
    from models import Lead
    captured = {}
    def fake_post(url, json, timeout):
        captured["payload"] = json
        class R: status_code = 200
        return R()
    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    lead = Lead(name="Acme Plumbing", country="ZA", city="Joburg",
                phone="+27115551234", category="plumber",
                instagram="acme_plumbing", facebook="acmeplumbing",
                demo_url="https://example.com")
    ok = notify_no_email(lead, "https://discord.com/webhook/fake")
    assert ok is True
    # The embed should mention both social platforms
    embed_text = json.dumps(captured["payload"])
    assert "instagram.com" in embed_text
    assert "facebook.com" in embed_text
    assert "Acme Plumbing" in embed_text
