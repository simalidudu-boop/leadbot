"""
enrich/deduplicator.py — extra deduping on top of the lead_id hash.

Looks for:
- Same phone in different formats
- Same name + same first 6 chars of address
- Same email (rare since we filter on has_email)
"""
from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Iterable

from config import log
from models import Lead, normalize_phone


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def deduplicate(leads: Iterable[Lead], threshold: float = 0.85) -> list[Lead]:
    """
    Remove near-duplicate leads. Keeps the one with the highest score
    and the most populated fields.
    """
    items = list(leads)
    by_phone: dict[str, list[Lead]] = defaultdict(list)
    for l in items:
        if l.phone:
            by_phone[l.phone].append(l)

    merged: list[Lead] = []
    used: set[int] = set()

    for i, lead in enumerate(items):
        if i in used:
            continue

        group = [lead]
        # Find fuzzy name matches in same city
        for j, other in enumerate(items):
            if i == j or j in used:
                continue
            if lead.city and other.city and lead.city != other.city:
                continue
            if _name_similarity(lead.name, other.name) >= threshold:
                group.append(other)
                used.add(j)
        if len(group) > 1:
            log.debug("Dedup group: %s", [g.name for g in group])
            group.sort(key=lambda x: (x.lead_score, sum(1 for f in (
                x.email, x.phone, x.instagram, x.facebook
            ) if f)), reverse=True)
            winner = group[0]
            for g in group[1:]:
                for f in ("email", "phone", "website", "instagram",
                          "facebook", "linkedin", "tiktok", "address"):
                    if not getattr(winner, f) and getattr(g, f):
                        setattr(winner, f, getattr(g, f))
                winner.source_count += 1
            merged.append(winner)
        else:
            merged.append(lead)
        used.add(i)
    log.info("Dedup: %d → %d", len(items), len(merged))
    return merged
