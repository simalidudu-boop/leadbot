"""
scrapers/base.py — orchestrator that runs every scraper and merges results.
"""
from __future__ import annotations

import logging
from typing import Iterable

from config import log
from models import Lead

from .overpass import scrape_overpass
from .geoapify import scrape_geoapify
from .opencorporates import scrape_opencorporates
from .yelp_fusion import scrape_yelp
from .yellowpages import scrape_yellowpages


def run_all_scrapers(settings) -> list[Lead]:
    """
    Run every available scraper, dedupe across sources, return merged list.
    Scrapers that lack API keys are silently skipped.
    """
    log.info("=== Scraping phase ===")
    sources: list[Iterable[Lead]] = []
    skipped: list[str] = []
    ran: list[str] = []

    if True:
        try:
            sources.append(scrape_overpass(settings))
            ran.append("overpass")
        except Exception as e:
            log.exception("overpass scraper failed: %s", e)
            skipped.append("overpass")

    if settings.geoapify_key:
        try:
            sources.append(scrape_geoapify(settings))
            ran.append("geoapify")
        except Exception as e:
            log.exception("geoapify scraper failed: %s", e)
            skipped.append("geoapify")
    else:
        skipped.append("geoapify (no key)")

    if settings.opencorporates_key:
        try:
            sources.append(scrape_opencorporates(settings))
            ran.append("opencorporates")
        except Exception as e:
            log.exception("opencorporates scraper failed: %s", e)
            skipped.append("opencorporates")
    else:
        skipped.append("opencorporates (no key)")

    if settings.yelp_api_key:
        try:
            sources.append(scrape_yelp(settings))
            ran.append("yelp")
        except Exception as e:
            log.exception("yelp scraper failed: %s", e)
            skipped.append("yelp")
    else:
        skipped.append("yelp (no key)")

    try:
        sources.append(scrape_yellowpages(settings))
        ran.append("yellowpages")
    except Exception as e:
        log.exception("yellowpages scraper failed: %s", e)
        skipped.append("yellowpages")

    log.info("Scrapers ran: %s | skipped: %s", ran, skipped)

    # Merge & dedupe by lead_id, boost score for multi-source matches
    merged: dict[str, Lead] = {}
    for source_list in sources:
        for lead in source_list:
            if not lead.name:
                continue
            if lead.is_chain():
                continue
            existing = merged.get(lead.lead_id)
            if existing:
                # merge contact fields if missing
                for f in ("email", "phone", "website", "instagram",
                          "facebook", "linkedin", "tiktok", "address"):
                    new_val = getattr(lead, f, "")
                    if new_val and not getattr(existing, f, ""):
                        setattr(existing, f, new_val)
                existing.source_count += 1
                existing.source = (existing.source + "," + lead.source).strip(",")
                # Re-score to pick up multi_source_match bonus
                from config import score_lead
                from dataclasses import asdict
                existing.lead_score, existing.score_breakdown = score_lead(
                    asdict(existing)
                )
            else:
                merged[lead.lead_id] = lead

    log.info("Unique leads after merge: %d", len(merged))
    return list(merged.values())
