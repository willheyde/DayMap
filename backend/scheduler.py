"""
scheduler.py

Runs alongside the FastAPI server inside Docker.
On startup: full morning sequence.
Every 2 hours: re-sync emails + calendar (keep data fresh).
Every morning at START_HOUR: full re-plan for the new day.

No cron. No cloud. Just a loop that wakes up every minute and checks.
"""

import time
import logging
from datetime import datetime, date as date_
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from emailParser import run_email_sync
from calendarSync import run_calendar_sync
from planner import run_planner

logging.basicConfig(
    level=logging.INFO,
    format="[scheduler] %(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configurable ────────────────────────────────────────────────────────────
START_HOUR        = 6      # hour to run the daily plan (6am)
SYNC_INTERVAL_HRS = 2      # how often to re-sync email + calendar
# ────────────────────────────────────────────────────────────────────────────


def job_sync():
    """Email + calendar sync. Safe to run repeatedly — both are idempotent."""
    log.info("── sync starting ──")
    try:
        email_result = run_email_sync()
        log.info(f"email sync done: {email_result}")
    except Exception as e:
        log.error(f"email sync failed: {e}")

    try:
        cal_result = run_calendar_sync()
        log.info(f"calendar sync done: {cal_result}")
    except Exception as e:
        log.error(f"calendar sync failed: {e}")


def job_plan():
    """Full morning sequence: sync first so the planner has fresh data."""
    log.info("── daily plan starting ──")
    job_sync()
    try:
        tasks = run_planner()
        log.info(f"planner done: {len(tasks)} task(s) generated")
    except Exception as e:
        log.error(f"planner failed: {e}")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/New_York")

    # Daily plan at START_HOUR
    scheduler.add_job(
        job_plan,
        CronTrigger(hour=START_HOUR, minute=0),
        id="daily_plan",
        name="Daily morning plan",
        replace_existing=True,
    )

    # Sync every N hours (offset by 1hr so it doesn't collide with the morning run)
    scheduler.add_job(
        job_sync,
        IntervalTrigger(hours=SYNC_INTERVAL_HRS),
        id="periodic_sync",
        name="Periodic sync",
        replace_existing=True,
    )

    # Run the full plan immediately on startup — don't wait for 6am
    log.info("Running startup sequence...")
    job_plan()

    log.info(f"Scheduler running. Daily plan at {START_HOUR}:00, sync every {SYNC_INTERVAL_HRS}h.")
    scheduler.start()