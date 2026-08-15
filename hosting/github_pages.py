"""
hosting/github_pages.py — deploy to GitHub Pages.

Each lead gets a repo named demo-<slug>-<id> under your org. The repo
must be public for Pages to be free. We push a single index.html to
the `main` branch, which Pages serves at:
    https://<org>.github.io/<repo>/
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from config import log
from http_client import get, post, put, delete
from models import Lead


def _slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "biz"


class GitHubPagesHost:
    def __init__(self, token: str, org: str):
        self.token = token
        self.org = org
        self.api = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def is_configured(self) -> bool:
        return bool(self.token and self.org)

    def deploy(self, lead: Lead, html_path: Path) -> Optional[str]:
        if not self.is_configured():
            return None
        slug = _slugify(lead.name)[:30]  # keep repo name short
        repo_name = f"demo-{slug}-{lead.lead_id[:6]}"
        html = html_path.read_text(encoding="utf-8")

        # 1. Create repo (idempotent: ignore 422 "already exists")
        r = post(
            f"{self.api}/orgs/{self.org}/repos",
            json_body={
                "name": repo_name,
                "private": False,
                "description": f"Demo site for {lead.name}",
                "auto_init": True,
                "has_pages": True,
            },
            headers=self.headers,
            timeout=30,
        )
        if r.status_code not in (201, 422):
            log.warning("GitHub repo create HTTP %d: %s",
                        r.status_code, r.text[:200])
            # Fall through; sometimes 422 means "already exists" and we
            # can still update contents.

        # 2. Enable Pages
        put(
            f"{self.api}/repos/{self.org}/{repo_name}/pages",
            json_body={
                "source": {"branch": "main", "path": "/"},
            },
            headers=self.headers,
            timeout=30,
        )

        # 3. Upload index.html
        content_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
        put(
            f"{self.api}/repos/{self.org}/{repo_name}/contents/index.html",
            json_body={
                "message": f"Demo for {lead.name}",
                "content": content_b64,
                "branch": "main",
            },
            headers=self.headers,
            timeout=30,
        )

        return f"https://{self.org}.github.io/{repo_name}/"
