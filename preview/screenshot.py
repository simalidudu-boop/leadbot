"""
preview/screenshot.py — render a URL and save a PNG screenshot.

Uses Playwright (Chromium). Falls back to a simple HTML+CSS placeholder
if Playwright is unavailable, so the email still goes out.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from config import PROJECT_ROOT, log


SHOTS_DIR = PROJECT_ROOT / "data" / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def screenshot_url(url: str, out_name: str,
                   *, width: int = 1200, height: int = 800,
                   timeout_ms: int = 30000) -> Optional[Path]:
    """
    Render `url` and write a PNG to data/screenshots/<out_name>.

    Returns the path on success, None on failure.
    """
    out_path = SHOTS_DIR / out_name
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
                ),
            )
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            # tiny extra wait for fonts
            page.wait_for_timeout(500)
            page.screenshot(path=str(out_path), full_page=False)
            browser.close()
        log.info("Screenshot saved: %s (%d bytes)",
                 out_path, out_path.stat().st_size)
        return out_path
    except Exception as e:
        log.warning("Playwright screenshot failed for %s: %s", url, e)
        return _placeholder_screenshot(out_path, url)


def _placeholder_screenshot(out_path: Path, url: str) -> Optional[Path]:
    """
    Fallback: write a tiny PNG placeholder (gray box + text). Better than
    nothing for the email.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1200, 800), color=(245, 245, 245))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        d.text((40, 40), "Demo preview unavailable", fill=(120, 120, 120), font=font)
        d.text((40, 80), f"Open in browser: {url}", fill=(80, 80, 80), font=font)
        img.save(out_path)
        return out_path
    except Exception as e:
        log.error("Even placeholder screenshot failed: %s", e)
        return None
