"""
hosting/netlify.py — deploy to Netlify (free, 100 GB bandwidth/mo).

Uses Netlify's zip-deploy API: POST a zip containing index.html to
/api/v1/sites, get back a URL.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Optional

from config import log
from models import Lead


class NetlifyHost:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/zip",
        }

    def is_configured(self) -> bool:
        return bool(self.token)

    def deploy(self, lead: Lead, html_path: Path) -> Optional[str]:
        if not self.is_configured():
            return None
        slug = re.sub(r"[^a-z0-9]+", "-", lead.name.lower()).strip("-")[:30] or "biz"
        site_name = f"demo-{slug}-{lead.lead_id[:6]}"

        # Build a zip in memory with just index.html
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("index.html", html_path.read_text(encoding="utf-8"))
        buf.seek(0)

        import requests
        r = requests.post(
            f"https://api.netlify.com/api/v1/sites/{site_name}",
            headers=self.headers,
            data=buf.read(),
            timeout=60,
        )
        if r.status_code not in (200, 201):
            # Site might already exist; try the deploys endpoint
            r2 = requests.post(
                f"https://api.netlify.com/api/v1/sites/{site_name}/deploys",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/zip",
                },
                data=buf.read(),
                timeout=60,
            )
            if r2.status_code not in (200, 201):
                log.warning("Netlify deploy HTTP %d: %s", r2.status_code, r2.text[:200])
                return None
        return f"https://{site_name}.netlify.app/"
