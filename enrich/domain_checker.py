"""
enrich/domain_checker.py — check if a domain is registered / has DNS.

Uses free RDAP via rdap.org which doesn't require any key. If a domain
has DNS records, it's likely live (and thus the business has *some*
online presence we should respect).
"""
from __future__ import annotations

from config import log
from http_client import get_json


def is_live_domain(domain: str) -> bool:
    """Returns True if RDAP says the domain is registered."""
    if not domain or "." not in domain:
        return False
    try:
        data = get_json(f"https://rdap.org/domain/{domain}")
        if not data:
            return False
        return "handle" in data or "ldhName" in data
    except Exception as e:
        log.debug("RDAP check failed for %s: %s", domain, e)
        return False
