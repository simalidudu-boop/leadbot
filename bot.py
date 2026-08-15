"""
bot.py — main orchestrator. Implements the 8-step flow:

  1. WAKE
  2. HUNT (scrape)
  3. EMAIL CHECK
  4. BUILD DEMO
  5. SEND + TRACK
  6. NO-EMAIL BRANCH
  7. FOLLOW-UP LOOP
  8. SLEEP
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Make sibling imports work whether run as `python bot.py` or `python -m leadbot.bot`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Settings, log, COUNTRIES, is_chain  # noqa
from models import Lead, is_valid_email  # noqa
import notion_crm as sheets  # noqa — keeping the alias so the rest of the code unchanged
from notion_crm import load_settings as load_crm_settings, load_templates
from state import load as load_state, save, increment_emails  # noqa
from scrapers import run_all_scrapers  # noqa
from enrich.contact_extractor import enrich_lead  # noqa
from enrich.deduplicator import deduplicate  # noqa
from ai.site_generator import generate_demo_site, generate_screenshot_filename  # noqa
from hosting.deployer import deploy_demo  # noqa
from preview.screenshot import screenshot_url  # noqa
from outreach.email_providers import send_email  # noqa
from outreach.templates import render_template  # noqa
from outreach.followup_scheduler import run_followup_loop  # noqa
from dm import dm_lead  # noqa
from notify.discord import notify_no_email, notify_error  # noqa


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────
def _slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())[:20] or "yourbusiness"


def _tld(country: str) -> str:
    return {
        "ZA": "co.za", "ZW": "co.zw", "ZM": "co.zm",
        "BW": "co.bw", "KE": "co.ke",
    }.get(country, "com")


def _in_send_window(settings, lead_country: str) -> bool:
    """True if the current UTC time falls within the lead's local send window."""
    from datetime import datetime
    offset = settings.timezone_offsets.get(lead_country, 2)
    now_local_hour = (datetime.utcnow().hour + offset) % 24
    return settings.send_window_local_start <= now_local_hour < settings.send_window_local_end


def _daily_cap_for(settings, country: str) -> int:
    raw = load_crm_settings().get("per_country_caps", "")
    if raw:
        try:
            for chunk in raw.split(","):
                k, v = chunk.split(":")
                if k.strip() == country:
                    return int(v.strip())
        except Exception:
            pass
    return max(1, settings.daily_email_cap // max(1, len(settings.countries)))


def _warmup_cap(settings) -> int:
    """If warmup mode is active, scale the cap based on days since first run."""
    state = load_state()
    started = state.get("warmup_started_at")
    if not started:
        # First run — initialize warmup
        from datetime import datetime
        state["warmup_started_at"] = datetime.utcnow().isoformat()
        save(state)
        started = state["warmup_started_at"]
    try:
        from datetime import datetime
        start_dt = datetime.fromisoformat(started)
        days = (datetime.utcnow() - start_dt).days
    except Exception:
        return settings.daily_email_cap
    if days >= settings.warmup_days:
        return settings.daily_email_cap
    # ramp 1 → cap
    return max(1, int((days + 1) / settings.warmup_days * settings.daily_email_cap))


# ────────────────────────────────────────────────────────────────────
# Step 2: Hunt
# ────────────────────────────────────────────────────────────────────
def step_hunt(settings) -> list[Lead]:
    log.info("=" * 60)
    log.info("STEP 2: HUNT — scraping free data sources")
    log.info("=" * 60)
    leads = run_all_scrapers(settings)
    if not leads:
        log.warning("No leads from scrapers")
        return []

    log.info("Enriching %d leads...", len(leads))
    enriched: list[Lead] = []
    for lead in leads:
        # Filter out chains (defense in depth)
        if lead.is_chain():
            continue
        try:
            enrich_lead(lead, serpapi_key=settings.serpapi_key)
        except Exception as e:
            log.debug("enrich failed for %s: %s", lead.name, e)
        enriched.append(lead)

    enriched = deduplicate(enriched)

    # Filter: must NOT have a website (our core value prop)
    without_site = [l for l in enriched if not l.has_website()]
    log.info("Leads without a website: %d / %d",
             len(without_site), len(enriched))
    return without_site


# ────────────────────────────────────────────────────────────────────
# Step 3+4+5: Build demo + email
# ────────────────────────────────────────────────────────────────────
def step_process_leads(leads: list[Lead], settings) -> None:
    log.info("=" * 60)
    log.info("STEP 3-5: Email check → build demo → send")
    log.info("=" * 60)

    state = load_state()
    global_cap = _warmup_cap(settings)
    sent_today = state.get("emails_sent_today", 0)
    if sent_today >= global_cap:
        log.info("Global daily cap reached (%d); skipping sends today", global_cap)
        return

    # Sort by score desc — best leads first
    leads.sort(key=lambda l: l.lead_score, reverse=True)

    # Track per-country caps
    country_sent: dict[str, int] = {}

    for lead in leads:
        # Global cap
        if state.get("emails_sent_today", 0) >= global_cap:
            log.info("Global cap reached; stopping")
            break

        # Per-country cap
        cap = _daily_cap_for(settings, lead.country)
        if country_sent.get(lead.country, 0) >= cap:
            log.debug("Country cap reached for %s", lead.country)
            continue

        # Send window check
        if not _in_send_window(settings, lead.country):
            log.debug("Outside send window for %s; skipping", lead.country)
            continue

        # Domain paused?
        from state import load as _load
        st = _load()
        paused = st.get("paused_domains") or set()
        if isinstance(paused, list):
            paused = set(paused)
        if lead.email and "@" in lead.email:
            dom = lead.email.split("@", 1)[1].lower()
            if dom in paused:
                log.info("Skipping %s — domain %s paused", lead.name, dom)
                continue

        # Already in CRM? skip
        if sheets.lead_exists(lead.lead_id):
            log.debug("Lead %s already in CRM; skipping", lead.lead_id)
            continue

        # ── Step 3: email check ──
        if not lead.has_email():
            log.info("No email for %s → no-email branch", lead.name)
            step_no_email_branch(lead, settings)
            continue

        log.info("Processing lead: %s (%s, %s) score=%d",
                 lead.name, lead.city, lead.country, lead.lead_score)

        # ── Step 4: build demo ──
        html_path, _ = generate_demo_site(lead, settings, dry_run=settings.dry_run)
        if not html_path:
            log.warning("Site generation failed for %s; sending without demo", lead.name)
        else:
            url = deploy_demo(lead, html_path, settings)
            if url:
                lead.demo_url = url
                log.info("Demo live: %s", url)
                # Take a screenshot for the email
                shot = screenshot_url(url, generate_screenshot_filename(lead))
                if shot:
                    lead.screenshot_url = _to_data_url(shot)
                else:
                    lead.screenshot_url = ""

        # ── Step 5: send email ──
        templates = load_templates()
        init = templates.get("email_initial") or {}
        subject = render_template(
            init.get("subject", "I built a quick website for {{business_name}}"),
            lead,
            suggested_domain=f"{_slugify(lead.name)}.{_tld(lead.country)}",
            sender_name=settings.from_name,
            sender_email=settings.from_email,
        )
        body = render_template(
            init.get("body", ""),
            lead,
            suggested_domain=f"{_slugify(lead.name)}.{_tld(lead.country)}",
            sender_name=settings.from_name,
            sender_email=settings.from_email,
        )

        attachments = []
        if html_path and lead.screenshot_url == "":
            # screenshot was inline; don't double-attach
            pass

        ok = send_email(
            lead, subject=subject, body=body,
            settings=settings, attachments=attachments,
        )
        if ok:
            from datetime import datetime
            now = datetime.utcnow().isoformat()
            add_lead(lead)
            update_lead_status(
                lead.lead_id, "Contacted",
                demo_url=lead.demo_url,
                screenshot_url=lead.screenshot_url,
                first_sent_at=now,
                last_touch_at=now,
                followup_count=0,
            )
            state = increment_emails()
            country_sent[lead.country] = country_sent.get(lead.country, 0) + 1
        else:
            add_lead(lead)   # record the attempt even if send failed
            update_lead_status(lead.lead_id, "New")
            log_event("email_send_failed", lead.lead_id, lead.email, "ERROR")


# ────────────────────────────────────────────────────────────────────
# Step 6: no-email branch
# ────────────────────────────────────────────────────────────────────
def step_no_email_branch(lead: Lead, settings) -> None:
    """
    Lead has no email. Flow:
      1. Build a demo site anyway (so the human has a link to send)
      2. Record the lead in the No Email Notion database
      3. Ping Discord with clickable social links so the human can
         reach out via IG/FB/LinkedIn manually
    No automated DMs are sent.
    """
    log.info("[no-email] %s — socials ig=%s fb=%s li=%s",
             lead.name, bool(lead.instagram), bool(lead.facebook),
             bool(lead.linkedin))

    # 1. Build a demo so the human has something to share
    html_path, _ = generate_demo_site(lead, settings, dry_run=settings.dry_run)
    if html_path:
        url = deploy_demo(lead, html_path, settings)
        if url:
            lead.demo_url = url
            shot = screenshot_url(url, generate_screenshot_filename(lead))
            if shot:
                lead.screenshot_url = _to_data_url(shot)

    # 2. Record in No Email database
    sheets.add_no_email_lead(lead, discord_notified=False)

    # 3. Ping Discord with clickable socials
    if settings.discord_webhook_url:
        ok = notify_no_email(lead, settings.discord_webhook_url)
        if ok:
            sheets.add_no_email_lead(lead, discord_notified=True)


def _to_data_url(shot_path: Path) -> str:
    """For the screenshot_url column, just store the local file path.
    When using Playwright you could also upload to a free image host
    (catbox.moe, imgur anonymous) and store that URL instead.
    """
    return f"file://{shot_path.absolute()}"


def _col_index_to_letter(idx: int) -> str:
    result = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def _split_for_subrun(leads, subrun: int, total: int) -> list:
    """
    Distribute today's leads across `total` sub-runs. Round-robin so
    each sub-run gets a balanced mix of high-score and lower-score leads.
    """
    if subrun < 1 or subrun > total:
        return leads
    # leads is already sorted by score desc (in step_process_leads)
    # so taking every Nth gives a fair spread
    return [l for i, l in enumerate(leads) if i % total == (subrun - 1)]


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Lead-Gen Bot")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually send/deploy")
    parser.add_argument("--scrape-only", action="store_true",
                        help="Only run scrapers, skip email/followup")
    parser.add_argument("--followups-only", action="store_true",
                        help="Only run the follow-up loop")
    parser.add_argument("--test-lead", type=str, default="",
                        help="Process a specific lead by name (for testing)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("🌍 Lead Bot starting — %s", datetime.utcnow().isoformat())
    log.info("=" * 60)

    settings = Settings.load()
    if args.dry_run:
        settings.dry_run = True

    # Master kill switch
    sheet_settings = load_crm_settings()
    if sheet_settings.get("pause_all", "").upper() in ("TRUE", "1", "YES"):
        log.warning("Settings!pause_all is TRUE — exiting")
        return

    # STEP 7 (first, so any scraped leads get immediate follow-ups)
    if not args.scrape_only:
        try:
            sent = run_followup_loop(settings)
            log.info("Follow-up loop sent %d emails", sent)
        except Exception as e:
            log.exception("Follow-up loop crashed: %s", e)
            notify_error(f"Follow-up loop crashed: {e}",
                         settings.discord_webhook_url)

    if args.followups_only:
        log.info("--followups-only: exiting")
        return

    # STEP 2: HUNT
    try:
        leads = step_hunt(settings)
    except Exception as e:
        log.exception("Hunt step crashed: %s", e)
        notify_error(f"Hunt step crashed: {e}", settings.discord_webhook_url)
        return

    # Sub-run slot: if we're in one of the 3 sub-runs, only process
    # the corresponding third of today's leads.
    if not args.test_lead and os.getenv("LEADBOT_SUBRUN"):
        try:
            subrun = int(os.getenv("LEADBOT_SUBRUN", "1"))
            total_subs = 3
            leads = _split_for_subrun(leads, subrun, total_subs)
        except ValueError:
            pass

    # Test-lead filter
    if args.test_lead:
        leads = [l for l in leads if args.test_lead.lower() in l.name.lower()]
        log.info("Filtered to %d leads matching '%s'", len(leads), args.test_lead)

    # STEP 3-6
    if not args.scrape_only:
        try:
            step_process_leads(leads, settings)
        except Exception as e:
            log.exception("Process step crashed: %s", e)
            notify_error(f"Process step crashed: {e}",
                         settings.discord_webhook_url)

    # STEP 8: sleep (handled by cron in real life)
    log.info("=" * 60)
    log.info("💤 Done. State saved. Next wake in 6 hours.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
