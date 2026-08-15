"""
hosting/deployer.py — orchestrate deploys with provider fallback.

Tries GitHub Pages → Cloudflare Pages → Netlify. First one that
succeeds wins.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import log
from models import Lead

from .github_pages import GitHubPagesHost
from .cloudflare_pages import CloudflarePagesHost
from .netlify import NetlifyHost


def deploy_demo(lead: Lead, html_path: Path, settings) -> Optional[str]:
    """
    Returns the public URL of the deployed demo, or None if all hosts
    failed.
    """
    if not html_path or not html_path.exists():
        return None

    chain = [
        ("github_pages",
         GitHubPagesHost(settings.github_token, settings.github_demo_org)),
        ("cloudflare_pages",
         CloudflarePagesHost(settings.cloudflare_pages_api_token,
                             settings.cloudflare_pages_account_id)),
        ("netlify", NetlifyHost(settings.netlify_token)),
    ]

    for name, host in chain:
        if not host.is_configured():
            log.debug("Host %s not configured, skipping", name)
            continue
        try:
            log.info("Deploying to %s...", name)
            url = host.deploy(lead, html_path)
            if url:
                log.info("Deployed to %s → %s", name, url)
                return url
        except Exception as e:
            log.warning("Deploy to %s failed: %s", name, e)

    log.error("All hosting providers failed for %s", lead.name)
    return None
