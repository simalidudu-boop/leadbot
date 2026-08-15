"""
hosting/cloudflare_pages.py — deploy to Cloudflare Pages (free, unlimited).

Uses Cloudflare's Direct Upload flow: ask for a signed upload URL, PUT
the HTML to it, done. Free, no card.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from config import log
from http_client import get, post, put
from models import Lead


class CloudflarePagesHost:
    def __init__(self, api_token: str, account_id: str):
        self.api_token = api_token
        self.account_id = account_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        return bool(self.api_token and self.account_id)

    def deploy(self, lead: Lead, html_path: Path) -> Optional[str]:
        if not self.is_configured():
            return None
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", lead.name.lower()).strip("-")[:30] or "biz"
        project_name = f"demo-{slug}-{lead.lead_id[:6]}"

        # 1. Create project (ignore 409 "already exists")
        r = post(
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/pages/projects",
            json_body={
                "name": project_name,
                "production_branch": "main",
            },
            headers=self.headers,
            timeout=30,
        )
        if r.status_code not in (200, 201, 409):
            log.warning("Cloudflare Pages create HTTP %d: %s",
                        r.status_code, r.text[:200])

        # 2. Direct upload (a single file deploy)
        # POST to /pages/assets/upload -> get a presigned URL
        up = post(
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/pages/assets/upload",
            json_body={},
            headers=self.headers,
            timeout=30,
        )
        if up.status_code not in (200, 201):
            log.warning("Cloudflare upload URL HTTP %d: %s",
                        up.status_code, up.text[:200])
            return None
        upload_url = (up.json().get("result") or {}).get("upload_url")
        if not upload_url:
            return None

        # 3. PUT the manifest + files. For a single file we use the
        # simpler /deployments endpoint.
        html = html_path.read_text(encoding="utf-8")
        # Use the deployments endpoint with a single-file manifest
        files = {
            "manifest": (None, '{"index.html":"index.html"}'),
            "index.html": ("index.html", html, "text/html"),
        }
        r = requests_post_multipart(upload_url, files=files)
        if r.status_code not in (200, 201):
            log.warning("Cloudflare deploy HTTP %d: %s", r.status_code, r.text[:200])
            return None

        return f"https://{project_name}.pages.dev/"


def requests_post_multipart(url, files):
    """Cloudflare wants a real multipart upload, not UrlFetch-style JSON."""
    import requests
    return requests.post(url, files=files, timeout=60)
