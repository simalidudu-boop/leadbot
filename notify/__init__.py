"""
notify package — push notifications (Discord webhooks).
"""
from .discord import notify_no_email, notify_error

__all__ = ["notify_no_email", "notify_error"]
