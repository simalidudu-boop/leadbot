"""
outreach package — sending, templates, follow-ups.
"""
from .email_providers import send_email
from .followup_scheduler import run_followup_loop

__all__ = ["send_email", "run_followup_loop"]
