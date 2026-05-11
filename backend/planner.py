import json
import httpx
from datetime import date as date_, datetime, timedelta
from Service import TaskService, ContactService, EmailService, CalendarEventService

OLLAMA_URL   = "http://host.docker.internal:11434/api/generate"
OLLAMA_MODEL = "llama3"
MAX_RETRIES  = 3

task_svc    = TaskService()
contact_svc = ContactService()
email_svc   = EmailService()
event_svc   = CalendarEventService()


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _to_dt(value) -> datetime | None:
    """
    Normalise a DB value to a datetime object.
    psycopg2 may return datetime objects directly, or ISO strings —
    this handles both so the rest of the code doesn't have to care.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date_) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _to_date_str(value) -> str | None:
    """Return a YYYY-MM-DD string from a date, datetime, or ISO string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_):
        return value.isoformat()
    # assume string — take first 10 chars
    return str(value)[:10]


def _duration_minutes(start, end) -> int | None:
    """Gap in minutes between two values (datetime objects or ISO strings)."""
    s = _to_dt(start)
    e = _to_dt(end)
    if s is None or e is None:
        return None
    try:
        return int((e - s).total_seconds() / 60)
    except Exception:
        return None


# ─────────────────────────────────────────────
#  CONTEXT BUILDER
# ─────────────────────────────────────────────

def _build_week_context(today: date_) -> list[dict]:
    """
    For each of the next 7 days, return:
      - date string
      - day name (Monday, Tuesday, ...)
      - list of event title + time strings
      - total blocked minutes
      - estimated free minutes (assuming 8am–11pm = 900 min usable day)
 
    The planner uses this to decide how to distribute work across the week
    before a deadline — front-loading onto lighter days, easing off heavy ones.
    """
    USABLE_DAY_MINUTES = 15 * 60   # 8am–11pm
 
    week = []
    for offset in range(1, 8):   # tomorrow through 7 days out
        day        = today + timedelta(days=offset)
        day_str    = day.isoformat()
        day_name   = day.strftime("%A")
 
        events     = event_svc.get_range(day_str, day_str)
        event_strs = []
        blocked    = 0
 
        for e in events:
            start_dt = _to_dt(e["start_time"])
            end_dt   = _to_dt(e["end_time"])
            mins     = _duration_minutes(start_dt, end_dt) or 0
            blocked += mins
            if start_dt:
                event_strs.append(f"{e['title']} ({start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M') if end_dt else '?'})")
 
        week.append({
            "date":            day_str,
            "day_name":        day_name,
            "events":          event_strs,
            "blocked_minutes": blocked,
            "free_minutes":    max(0, USABLE_DAY_MINUTES - blocked),
        })
 
    return week
 
 
def _build_context() -> dict:
    today     = date_.today()
    today_str = today.isoformat()
    lookahead = (today + timedelta(days=7)).isoformat()
 
    # ── Today's blocked time ──────────────────────────────────────────────────
    events_today = event_svc.get_today()
    blocked_windows = []
    for e in events_today:
        start_dt = _to_dt(e["start_time"])
        end_dt   = _to_dt(e["end_time"])
        blocked_windows.append({
            "title":            e["title"],
            "type":             e["event_type"],
            "start":            start_dt.strftime("%H:%M") if start_dt else None,
            "end":              end_dt.strftime("%H:%M")   if end_dt   else None,
            "duration_minutes": _duration_minutes(start_dt, end_dt),
        })
 
    USABLE_DAY_MINUTES = 15 * 60
    blocked_minutes    = sum(b["duration_minutes"] or 0 for b in blocked_windows)
    free_minutes       = max(0, USABLE_DAY_MINUTES - blocked_minutes)
 
    # ── Tasks — normalise due_date to string ──────────────────────────────────
    all_tasks = task_svc.get_all()
    for t in all_tasks:
        t["due_date"] = _to_date_str(t.get("due_date"))
 
    overdue = [
        t for t in all_tasks
        if t.get("due_date") and t["due_date"] < today_str
        and t["status"] in ("pending", "rolled")
    ]
    due_today = [
        t for t in all_tasks
        if t.get("due_date") == today_str
        and t["status"] in ("pending", "rolled")
    ]
    rolled = [
        t for t in all_tasks
        if t["status"] == "rolled" and not t.get("due_date")
    ]
    upcoming = [
        t for t in all_tasks
        if t.get("due_date")
        and today_str < t["due_date"] <= lookahead
        and t["status"] in ("pending", "rolled")
    ]
 
    emails   = email_svc.get_unactioned()
    contacts = contact_svc.get_targets_for_today(limit=5)
 
    # ── Week load map ─────────────────────────────────────────────────────────
    week_ahead = _build_week_context(today)
 
    return {
        "date":         today_str,
        "day_name":     today.strftime("%A"),
        "free_minutes": free_minutes,
 
        "blocked_time_today": blocked_windows,
 
        # The week load map — the key addition for multi-day planning
        "week_ahead": week_ahead,
 
        "overdue_tasks": [
            {
                "title":       t["title"],
                "category":    t["category"],
                "due_date":    t["due_date"],
                "days_overdue": (today - date_.fromisoformat(t["due_date"])).days,
                "days_rolled": t["rolled_over_count"],
            }
            for t in overdue[:5]
        ],
        "due_today": [
            {"title": t["title"], "category": t["category"]}
            for t in due_today[:5]
        ],
        "rolled_over_tasks": [
            {
                "title":       t["title"],
                "category":    t["category"],
                "days_rolled": t["rolled_over_count"],
                "is_optional": t["is_optional"],
            }
            for t in rolled[:8]
        ],
        "upcoming_due_dates": [
            {
                "title":           t["title"],
                "category":        t["category"],
                "due_date":        t["due_date"],
                "days_out":        (date_.fromisoformat(t["due_date"]) - today).days,
                "duration_minutes": t.get("duration_minutes", 30),
            }
            for t in sorted(upcoming, key=lambda x: x["due_date"])[:8]
        ],
        "unactioned_emails": [
            {
                "from":        e["sender_name"] or e["sender_address"],
                "subject":     e["subject"],
                "action_type": e["action_type"],
                "preview":     e["body_preview"],
            }
            for e in emails[:8]
        ],
        "contacts_to_reach": [
            {"name": c["name"], "company": c["company"], "role": c["role"]}
            for c in contacts
        ],
    }


# ─────────────────────────────────────────────
#  PROMPT BUILDER
# ─────────────────────────────────────────────

def _build_prompt(context: dict) -> str:
    return f"""
You are a personal day planner. Generate a realistic, well-distributed task list for TODAY only.
 
CONTEXT:
{json.dumps(context, indent=2)}
 
═══════════════════════════════════════════════
 PRIORITY TIERS
═══════════════════════════════════════════════
 
TIER 1 — Priority 1 (non-negotiable, schedule first):
  - Any task from overdue_tasks or due_today.
  - Email replies where the sender is clearly waiting.
  - Rolled tasks carried more than 3 days.
 
TIER 2 — Priority 2–3 (should do today):
  - Rolled tasks that are not optional.
  - New tasks from unactioned_emails or contacts_to_reach.
  - Deadline tasks where today is the right day to start (see MULTI-DAY rules below).
 
TIER 3 — Priority 4–5 (nice to do, only if free_minutes allows):
  - Optional or low-urgency tasks.
  - Mark is_optional: true.
 
═══════════════════════════════════════════════
 MULTI-DAY DISTRIBUTION (the most important section)
═══════════════════════════════════════════════
 
You have a week_ahead map showing how loaded each upcoming day is.
Use it to decide how much of a deadline task to schedule TODAY.
 
Rules:
 
1. FRONT-LOAD onto light days, ease off heavy days.
   - If today has lots of free_minutes and a deadline is in 3–5 days → schedule
     a substantial chunk today (45–90 min) so work is done before the sprint.
   - If today is already heavy (blocked_time_today is long) → schedule only a
     short chunk (20–30 min) and rely on lighter days ahead.
 
2. SIZE chunks based on days remaining and upcoming load.
   - days_out = 1 or 2: schedule the full estimated duration today — it's now or never.
   - days_out = 3–4: split roughly in half. Schedule one half today if today is light,
     otherwise schedule a smaller start chunk (30 min) and note the rest is for later.
   - days_out = 5–7: schedule a "get started" chunk (20–40 min) only if today is light.
     If today is heavy, skip it — there's time.
   - days_out > 7: do NOT schedule unless it's also in rolled_over_tasks.
 
3. AVOID piling onto days that already have heavy blocking.
   Look at week_ahead: if the day before the deadline has 300+ blocked minutes,
   don't assume the user can finish it then — pull work earlier.
 
4. ONE task per deadline item per day.
   Do not create multiple tasks for the same deadline. Create one, size it correctly,
   and note in the `notes` field what's left (e.g. "first half — ~60 min remaining").
 
═══════════════════════════════════════════════
 SCHEDULING RULES
═══════════════════════════════════════════════
 
  - Never overlap a window in blocked_time_today.
  - Sum of all task duration_minutes ≤ free_minutes for today.
  - Total tasks: 3 minimum, 8 maximum. Fewer on heavy days.
  - A day with 4+ hours blocked → max 3–4 tasks, keep them short.
  - Be realistic. Don't fill every minute.
 
═══════════════════════════════════════════════
 OUTPUT FORMAT
═══════════════════════════════════════════════
 
Respond with ONLY a JSON array. No explanation, no markdown, no backticks, no code fences.
 
[
  {{
    "title": "Start Lab 4 writeup — intro + methods",
    "category": "school",
    "duration_minutes": 60,
    "priority": 2,
    "is_optional": false,
    "due_date": "2026-05-15",
    "notes": "Due Thursday. Light day today — get the structure done now, ~45 min left after this."
  }}
]
 
Fields:
  title            — specific action, not vague ("start X section" beats "work on X")
  category         — work | school | network | hobby | errand
  duration_minutes — realistic estimate for TODAY's chunk only
  priority         — 1–5
  is_optional      — true only for tier 3
  due_date         — the actual deadline date, or null
  notes            — what chunk this is, what's left, or null
""".strip()


# ─────────────────────────────────────────────
#  LLM CALL
# ─────────────────────────────────────────────

def _call_llm(prompt: str) -> list[dict] | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=300) as client:
                response = client.post(OLLAMA_URL, json={
                    "model":  OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                })
            response.raise_for_status()
            raw = response.json().get("response", "").strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            tasks = json.loads(raw)
            if not isinstance(tasks, list):
                raise ValueError("Response was not a JSON array")

            print(f"[planner] LLM returned {len(tasks)} tasks on attempt {attempt}")
            return tasks

        except json.JSONDecodeError as e:
            print(f"[planner] Attempt {attempt}: bad JSON — {e}")
        except httpx.RequestError as e:
            print(f"[planner] Attempt {attempt}: Ollama unreachable — {e}")
            break
        except Exception as e:
            print(f"[planner] Attempt {attempt}: unexpected error — {e}")

    print("[planner] All attempts failed. Falling back to existing tasks.")
    return None


# ─────────────────────────────────────────────
#  FALLBACK
# ─────────────────────────────────────────────

def _fallback_tasks() -> list[dict]:
    existing = task_svc.get_all()
    pending  = [t for t in existing if t["status"] in ("pending", "rolled")]
    print(f"[planner] Using {len(pending)} fallback tasks from DB")
    return pending


# ─────────────────────────────────────────────
#  SEED EVENT TASKS
#
#  Every calendar event today gets a corresponding task so it appears
#  in the user's task list — not just as blocked time.
#  The linked_event_id prevents duplicate tasks on re-runs.
# ─────────────────────────────────────────────

def _seed_event_tasks(events_today: list[dict]) -> list[dict]:
    all_tasks      = task_svc.get_all()
    already_linked = {t["linked_event_id"] for t in all_tasks if t.get("linked_event_id")}

    seeded = []

    for event in events_today:
        event_id = event["id"]
        if event_id in already_linked:
            continue

        event_type = event["event_type"]
        title      = event["title"]

        # ── Normalise datetimes from psycopg2 ────────────────────────────────
        start_dt = _to_dt(event["start_time"])
        end_dt   = _to_dt(event["end_time"])
        duration = _duration_minutes(start_dt, end_dt) or 60

        due_date_str  = start_dt.date().isoformat() if start_dt else date_.today().isoformat()
        time_range    = (
            f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
            if start_dt and end_dt else None
        )

        # ── Map event type → task properties ─────────────────────────────────
        if event_type == "shift":
            category    = "work"
            priority    = 1
            is_optional = False
            task_title  = f"Work shift — {title}" if title.lower() not in ("work", "shift") else title
        elif event_type == "class_":
            category    = "school"
            priority    = 1
            is_optional = False
            task_title  = f"Attend {title}"
        elif event_type == "meeting":
            category    = "network"
            priority    = 1
            is_optional = False
            task_title  = f"Meeting — {title}"
        else:
            category    = "errand"
            priority    = 2
            is_optional = False
            task_title  = title

        task = {
            "title":             task_title,
            "category":          category,
            "duration_minutes":  duration,
            "priority":          priority,
            "is_optional":       is_optional,
            "due_date":          due_date_str,
            "source":            "planner",
            "status":            "pending",
            "rolled_over_count": 0,
            "created_date":      date_.today().isoformat(),
            "linked_contact_id": event.get("linked_contact_id"),
            "linked_event_id":   event_id,
            "notes":             f"Calendar event: {time_range}" if time_range else None,
        }

        new_id     = task_svc.create(task)
        task["id"] = new_id
        seeded.append(task)
        print(f"[planner] Seeded task #{new_id} from event '{title}' ({time_range})")

    return seeded


# ─────────────────────────────────────────────
#  SAVE LLM TASKS
# ─────────────────────────────────────────────

def _save_tasks(raw_tasks: list[dict]) -> list[dict]:
    saved = []
    for t in raw_tasks:
        try:
            if not t.get("title") or not t.get("category"):
                print(f"[planner] Skipping malformed task: {t}")
                continue

            task = {
                "title":             t["title"],
                "category":          t["category"],
                "duration_minutes":  t.get("duration_minutes", 30),
                "priority":          t.get("priority", 3),
                "is_optional":       t.get("is_optional", False),
                "due_date":          t.get("due_date"),
                "source":            "planner",
                "status":            "pending",
                "rolled_over_count": 0,
                "created_date":      date_.today().isoformat(),
                "linked_contact_id": None,
                "linked_event_id":   None,
                "notes":             t.get("notes"),
            }

            new_id     = task_svc.create(task)
            task["id"] = new_id
            saved.append(task)
            print(f"[planner] Saved task #{new_id} (p{task['priority']}): '{task['title']}'")

        except Exception as e:
            print(f"[planner] Failed to save task '{t.get('title', '?')}': {e}")

    return saved


# ─────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def run_planner() -> list[dict]:
    """
    Execution order:
      1. Seed tasks from today's calendar events — these show up in the task list
         AND the planner knows their windows are blocked.
      2. Build context with fresh data.
      3. LLM fills in the rest (emails, contacts, rolled tasks).
      4. Return seeded + LLM tasks together.
    """
    print(f"[planner] Running for {date_.today().isoformat()}...")

    events_today = event_svc.get_today()
    seeded       = _seed_event_tasks(events_today)
    print(f"[planner] Seeded {len(seeded)} task(s) from calendar events")

    context   = _build_context()
    prompt    = _build_prompt(context)
    raw_tasks = _call_llm(prompt)

    if raw_tasks is None:
        return _fallback_tasks()

    llm_tasks = _save_tasks(raw_tasks)
    return seeded + llm_tasks