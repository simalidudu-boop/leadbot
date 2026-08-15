"""
run.py — Railway entrypoint. Runs the bot in a loop with a scheduler.

Railway runs this as a long-lived worker (not a one-shot cron). The bot:
  1. Wakes up
  2. Runs the full pipeline
  3. Sleeps until the next scheduled time
  4. Repeats forever

The schedule is:
  - 09:00-11:00 CAT → run the bot
  - 11:00-15:00 CAT → sleep
  - 15:00-17:00 CAT → run the bot
  - 17:00-09:00 CAT → sleep
  - Repeat

The bot uses APScheduler for the timing. If APScheduler is unavailable
(free tier is strict on dependencies), it falls back to a simple
sleep-loop that checks the clock every minute.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Settings, log


# ────────────────────────────────────────────────────────────────────
# Scheduling constants
# ────────────────────────────────────────────────────────────────────
# We split the morning work window into 3 sub-runs to spread CPU,
# network, and AI load. 09:00 CAT, 09:40 CAT, 10:20 CAT.
# The 15:00 slot is gone — leads that don't fit in the morning get
# pushed to tomorrow morning's queue.
# All hours in UTC. 07:00 UTC = 09:00 CAT (SAST/ZWST).
# 07:00, 07:40, 08:20 UTC = 09:00, 09:40, 10:20 CAT.
RUN_HOURS_UTC = [7, 7 + 40 // 60, 8 + 20 // 60]   # = [7, 7, 8] but the
                                                    # actual minute is
                                                    # handled by the
                                                    # window logic below.
# More precise: use (hour, minute) tuples.
RUN_TIMES_UTC = [(7, 0), (7, 40), (8, 20)]


def _current_utc() -> datetime:
    return datetime.now()


def should_run_now() -> bool:
    """True if current UTC time is within any of today's run slots
    (each slot is a 15-minute window starting at the scheduled time)."""
    now = _current_utc()
    for hour, minute in RUN_TIMES_UTC:
        slot_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        slot_end = slot_start.replace(minute=minute + 15)
        if slot_start <= now < slot_end:
            return True
    return False


def time_until_next_window() -> int:
    """Seconds until the bot should next run."""
    now = _current_utc()
    today_slots = [
        now.replace(hour=h, minute=m, second=0, microsecond=0)
        for h, m in RUN_TIMES_UTC
    ]
    # Find the next slot today that's still in the future
    for slot in today_slots:
        if slot > now:
            return int((slot - now).total_seconds())
    # Otherwise first slot tomorrow
    tomorrow = (now + timedelta(days=1)).replace(
        hour=RUN_TIMES_UTC[0][0], minute=RUN_TIMES_UTC[0][1],
        second=0, microsecond=0
    )
    return int((tomorrow - now).total_seconds())


# ────────────────────────────────────────────────────────────────────
# Run the bot
# ────────────────────────────────────────────────────────────────────
def run_bot_once() -> None:
    """Invoke the bot's main function. Isolated so a crash here doesn't
    kill the whole loop."""
    subrun = _which_subrun()
    if subrun:
        os.environ["LEADBOT_SUBRUN"] = str(subrun)
        log.info("Detected sub-run slot %d/3 — will process 1/3 of leads", subrun)
    try:
        from bot import main as bot_main
        bot_main()
    except SystemExit:
        pass
    except Exception as e:
        log.exception("Bot run failed: %s", e)
        try:
            from notify.discord import notify_error
            settings = Settings.load()
            notify_error(f"Bot run failed: {e}", settings.discord_webhook_url)
        except Exception:
            pass


def _which_subrun() -> int:
    """Return 1/2/3 if we're currently inside one of the run slots, else 0."""
    now = _current_utc()
    for i, (hour, minute) in enumerate(RUN_TIMES_UTC, start=1):
        slot_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        slot_end = slot_start.replace(minute=minute + 15)
        if slot_start <= now < slot_end:
            return i
    return 0


# ────────────────────────────────────────────────────────────────────
# Graceful shutdown
# ────────────────────────────────────────────────────────────────────
_running = True


def _handle_signal(signum, frame):
    global _running
    log.info("Received signal %s, shutting down after current run", signum)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ────────────────────────────────────────────────────────────────────
# Main loop
# ────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=" * 60)
    log.info("🤖 Lead Bot worker starting (Railway)")
    log.info("   Run windows (UTC): %s", RUN_WINDOWS_UTC)
    log.info("=" * 60)

    # Run once on startup so the user sees results immediately
    if os.getenv("RUN_ON_STARTUP", "true").lower() in ("1", "true", "yes"):
        log.info("Initial run on startup...")
        run_bot_once()

    while _running:
        if should_run_now():
            log.info("⏰ Within run window — executing bot")
            run_bot_once()
            # Sleep until just past the current window
            wait = time_until_next_window()
            wait = min(wait, 60 * 60 * 3)   # never more than 3h
        else:
            wait = time_until_next_window()
            log.info("💤 Sleeping %d minutes until next run window",
                     wait // 60)

        # Sleep in 1-minute chunks so signals are responsive
        for _ in range(wait // 60 + 1):
            if not _running:
                break
            time.sleep(60)

    log.info("Worker stopped.")


if __name__ == "__main__":
    main()
