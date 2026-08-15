"""
http_client.py — shared HTTP wrapper with retries, timeouts, and rate-limit
awareness. Every scraper / AI / hosting / email module uses this.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import log

DEFAULT_TIMEOUT = 30


def make_session() -> requests.Session:
    """Session with automatic retry on common transient errors."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "LeadBot/1.0 (+https://example.com) python-requests",
        "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
    })
    return s


SESSION = make_session()


def get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None,
        timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    log.debug("GET %s params=%s", url, params)
    return SESSION.get(url, params=params, headers=headers, timeout=timeout)


def post(url: str, *, json_body: Optional[dict] = None,
         data: Any = None, headers: Optional[dict] = None,
         timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    log.debug("POST %s", url)
    return SESSION.post(url, json=json_body, data=data, headers=headers, timeout=timeout)


def put(url: str, *, json_body: Optional[dict] = None,
        data: Any = None, headers: Optional[dict] = None,
        timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    log.debug("PUT %s", url)
    return SESSION.put(url, json=json_body, data=data, headers=headers, timeout=timeout)


def delete(url: str, *, headers: Optional[dict] = None,
           timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    log.debug("DELETE %s", url)
    return SESSION.delete(url, headers=headers, timeout=timeout)


def get_json(url: str, **kwargs) -> Optional[Any]:
    """GET + JSON-decode, with graceful failure."""
    try:
        r = get(url, **kwargs)
        if r.status_code != 200:
            log.debug("GET %s → %d", url, r.status_code)
            return None
        return r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.debug("get_json %s failed: %s", url, e)
        return None


def post_json(url: str, **kwargs) -> Optional[Any]:
    try:
        r = post(url, **kwargs)
        if r.status_code != 200:
            log.debug("POST %s → %d", url, r.status_code)
            return None
        return r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.debug("post_json %s failed: %s", url, e)
        return None


def get_text(url: str, **kwargs) -> Optional[str]:
    try:
        r = get(url, **kwargs)
        if r.status_code != 200:
            return None
        return r.text
    except requests.RequestException as e:
        log.debug("get_text %s failed: %s", url, e)
        return None


def polite_sleep(seconds: float) -> None:
    """Sleep helper for rate-limit politeness."""
    if seconds > 0:
        time.sleep(seconds)
