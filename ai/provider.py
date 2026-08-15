"""
ai/provider.py — fallback chain for free-tier LLM providers.

Order: Cloudflare Workers AI (default, generous free tier) →
       Mistral → Cohere → Groq.

Each provider has a `generate(prompt) -> str` interface. The chain tries
each one in order until one returns content.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config import log
from http_client import post, get
from state import load, save


class AIError(Exception):
    pass


# ────────────────────────────────────────────────────────────────────
# Provider implementations
# ────────────────────────────────────────────────────────────────────
def _cloudflare_generate(prompt: str, system: str,
                         account_id: str, token: str) -> str:
    """Cloudflare Workers AI. Default model: llama-3.1-8b-instruct-fast."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/@cf/meta/llama-3.1-8b-instruct"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
    }
    r = post(url, json_body=body, headers=headers, timeout=60)
    if r.status_code != 200:
        raise AIError(f"cloudflare HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if not data.get("success"):
        raise AIError(f"cloudflare API error: {data}")
    content = (data.get("result") or {}).get("response", "")
    if not content:
        raise AIError("cloudflare returned empty response")
    return content


def _mistral_generate(prompt: str, system: str, key: str) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
    }
    r = post(url, json_body=body, headers=headers, timeout=60)
    if r.status_code != 200:
        raise AIError(f"mistral HTTP {r.status_code}: {r.text[:200]}")
    content = r.json()["choices"][0]["message"]["content"]
    if not content:
        raise AIError("mistral returned empty response")
    return content


def _cohere_generate(prompt: str, system: str, key: str) -> str:
    url = "https://api.cohere.com/v1/chat"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "command-r",
        "preamble": system,
        "message": prompt,
        "max_tokens": 4096,
    }
    r = post(url, json_body=body, headers=headers, timeout=60)
    if r.status_code != 200:
        raise AIError(f"cohere HTTP {r.status_code}: {r.text[:200]}")
    content = r.json().get("text", "")
    if not content:
        raise AIError("cohere returned empty response")
    return content


def _groq_generate(prompt: str, system: str, key: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
    }
    r = post(url, json_body=body, headers=headers, timeout=60)
    if r.status_code != 200:
        raise AIError(f"groq HTTP {r.status_code}: {r.text[:200]}")
    content = r.json()["choices"][0]["message"]["content"]
    if not content:
        raise AIError("groq returned empty response")
    return content


# ────────────────────────────────────────────────────────────────────
# Fallback chain
# ────────────────────────────────────────────────────────────────────
def generate(prompt: str, system: str, settings) -> str:
    """
    Try each configured provider in order. Returns the first successful
    response. Raises AIError only if all fail.
    """
    state = load()
    usage = state.get("ai_usage", {})

    chain: list[tuple[str, callable]] = []

    if settings.cloudflare_account_id and settings.cloudflare_api_token:
        # Skip cloudflare if it's already used 10k neurons today (heuristic)
        if usage.get("cloudflare", 0) < 9000:
            chain.append((
                "cloudflare",
                lambda p, s: _cloudflare_generate(
                    p, s, settings.cloudflare_account_id,
                    settings.cloudflare_api_token
                ),
            ))

    if settings.mistral_api_key:
        chain.append((
            "mistral",
            lambda p, s: _mistral_generate(p, s, settings.mistral_api_key),
        ))

    if settings.cohere_api_key:
        chain.append((
            "cohere",
            lambda p, s: _cohere_generate(p, s, settings.cohere_api_key),
        ))

    if settings.groq_api_key:
        chain.append((
            "groq",
            lambda p, s: _groq_generate(p, s, settings.groq_api_key),
        ))

    if not chain:
        raise AIError(
            "No AI provider configured. Set at least one of CLOUDFLARE_*, "
            "MISTRAL_API_KEY, COHERE_API_KEY, or GROQ_API_KEY."
        )

    last_err = None
    for name, fn in chain:
        try:
            log.info("AI: trying provider %s", name)
            content = fn(prompt, system)
            if content:
                usage[name] = usage.get(name, 0) + 1
                state["ai_usage"] = usage
                save(state)
                log.info("AI: %s succeeded (%d chars)", name, len(content))
                return content
        except Exception as e:
            log.warning("AI: %s failed: %s", name, e)
            last_err = e
            continue

    raise AIError(f"All AI providers failed. Last error: {last_err}")
