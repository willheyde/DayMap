"""
calendarSync.py

Fetches iCal subscription URLs and syncs them into the calendar_events table.
Called by:
  - scheduler.py  (nightly, alongside the planner)
  - POST /api/events/sync  (manual trigger from the frontend)

No OAuth. No API keys. Just URLs with tokens baked in — stored in .env.
Add as many ICAL_FEED_N entries as you have calendars.
"""

import os
import httpx
from dotenv import load_dotenv
from Service import CalendarEventService

load_dotenv()

event_svc = CalendarEventService()


# ─────────────────────────────────────────────
#  FEED DISCOVERY
#  Reads all ICAL_FEED_* keys from .env so you
#  can add more calendars without touching code.
# ─────────────────────────────────────────────

def _get_feed_urls() -> list[str]:
    """
    Collects every env var named ICAL_FEED_1, ICAL_FEED_2, ... ICAL_FEED_N.
    Returns them as a list, skipping any that are empty or missing.
    """
    feeds = []
    i = 1
    while True:
        url = os.getenv(f"ICAL_FEED_{i}", "").strip()
        if not url:
            break
        feeds.append(url)
        i += 1
    return feeds


# ─────────────────────────────────────────────
#  FETCH ONE FEED
# ─────────────────────────────────────────────

def _fetch_ical(url: str) -> str | None:
    """
    GETs the iCal URL and returns the raw text.
    Returns None on any network or HTTP error.
    """
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        print(f"[calendarSync] HTTP {e.response.status_code} fetching feed: {url[:60]}...")
        return None
    except httpx.RequestError as e:
        print(f"[calendarSync] Network error fetching feed: {e}")
        return None


# ─────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def run_calendar_sync() -> dict:
    """
    Fetches all configured iCal feeds and syncs them into calendar_events.
    Deduplication is handled by ical_uid — re-running this is always safe.
    Returns a summary dict for logging / the API response.
    """
    feeds = _get_feed_urls()

    if not feeds:
        print("[calendarSync] No ICAL_FEED_* URLs found in .env — nothing to sync.")
        return {"feeds_checked": 0, "total_imported": 0}

    total_imported = 0
    results        = []

    for i, url in enumerate(feeds, start=1):
        print(f"[calendarSync] Fetching feed {i}/{len(feeds)}: {url[:60]}...")
        ical_text = _fetch_ical(url)

        if ical_text is None:
            results.append({"feed": i, "status": "error", "imported": 0})
            continue

        try:
            imported = event_svc.import_ical(ical_text)
            print(f"[calendarSync] Feed {i}: {imported} new event(s) imported.")
            total_imported += imported
            results.append({"feed": i, "status": "ok", "imported": imported})
        except Exception as e:
            print(f"[calendarSync] Feed {i}: parse error — {e}")
            results.append({"feed": i, "status": "parse_error", "imported": 0})

    print(f"[calendarSync] Done. {total_imported} total new event(s) across {len(feeds)} feed(s).")
    return {
        "feeds_checked":  len(feeds),
        "total_imported": total_imported,
        "detail":         results,
    }