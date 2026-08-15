"""
Scrapers package — each module returns an iterable of Lead.
"""
from .base import run_all_scrapers  # re-export
__all__ = ["run_all_scrapers"]
