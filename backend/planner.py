import json
import httpx
from datetime import date as date_, datetime, timedelta
from Service import TaskService, ContactService, EmailService, CalendarEventService

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
MAX_RETRIES  = 3

task_svc    = TaskService()
contact_svc = ContactService()
email_svc   = EmailService()
event_svc   = CalendarEventService()   # replaces shift_svc


# ─────────────────────────────────────────────
#  CONTEXT BUILDER
# ─────────────────────────────────────────────

def _build_context() -> dict:
    today      = date_.today()
    today_str  = today.isoformat()
    lookahead  = (today + timedelta(days=7)).isoformat()

    # ── Time blocks: what's already locked in today ───────────────────────────
    events_today = event_svc.get_today()   # ordered by start_time from the DB
    blocked_windows = [
        {
            "title":      e["title"],
            "type":       e["event_type"],
            "start":      e["start_time"],
            "end":        e["end_time"],
            "duration_minutes": _duration_minutes(e["start_time"], e["end_time"]),
        }
        for e in events_today
    ]

    # Compute free minutes today so the LLM knows how much room it has
    total_day_minutes = 16 * 60   # assume 8am–midnight as the usable window
    blocked_minutes   = sum(b["duration_minutes"] or 0 for b in blocked_windows)
    free_minutes      = max(0, total_day_minutes - blocked_minutes)

    # ── Tier 1: overdue + due today ────────────────────────────────────────────
    all_tasks    = task_svc.get_all()
    overdue      = [
        t for t in all_tasks
        if t.get("due_date") and t["due_date"] < today_str
        and t["status"] in ("pending", "rolled")
    ]
    due_today    = [
        t for t in all_tasks
        if t.get("due_date") == today_str
        and t["status"] in ("pending", "rolled")
    ]

    # ── Tier 2: rolled tasks (no due date, user left them undone) ─────────────
    rolled = [
        t for t in all_tasks
        if t["status"] == "rolled"
        and not t.get("due_date")   # already captured above if they have one
    ]

    # ── Tier 3: upcoming due dates in the next 7 days ────────────────────────
    upcoming = [
        t for t in all_tasks
        if t.get("due_date")
        and today_str < t["due_date"] <= lookahead
        and t["status"] in ("pending", "rolled")
    ]

    # ── Emails and contacts (same as before) ─────────────────────────────────
    emails   = email_svc.get_unactioned()
    contacts = contact_svc.get_targets_for_today(limit=5)

    return {
        "date":         today_str,
        "free_minutes": free_minutes,   # how much unblocked time exists today

        # The planner must not schedule tasks inside these windows
        "blocked_time_today": blocked_windows,

        # Tier 1 — non-negotiable
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
            {
                "title":    t["title"],
                "category": t["category"],
            }
            for t in due_today[:5]
        ],

        # Tier 2 — user left these undone, surface them
        "rolled_over_tasks": [
            {
                "title":       t["title"],
                "category":    t["category"],
                "days_rolled": t["rolled_over_count"],
                "is_optional": t["is_optional"],
            }
            for t in rolled[:8]
        ],

        # Tier 3 — upcoming, worth starting early if there's room
        "upcoming_due_dates": [
            {
                "title":    t["title"],
                "category": t["category"],
                "due_date": t["due_date"],
                "days_out": (date_.fromisoformat(t["due_date"]) - today).days,
            }
            for t in sorted(upcoming, key=lambda x: x["due_date"])[:5]
        ],

        # New tasks to generate from live data
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
            {
                "name":    c["name"],
                "company": c["company"],
                "role":    c["role"],
            }
            for c in contacts
        ],
    }


# ─────────────────────────────────────────────
#  PROMPT BUILDER
# ─────────────────────────────────────────────

def _build_prompt(context: dict) -> str:
    return f"""
You are a personal day planner. Based on the context below, generate a realistic task list for today.

CONTEXT:
{json.dumps(context, indent=2)}

PRIORITY TIERS — assign priority strictly according to these rules:

  TIER 1 — Priority 1 (must do today, schedule first):
    - Any task from overdue_tasks or due_today.
    - Any email reply or follow-up where the sender is waiting.
    - Any rolled task that has been carried more than 3 days.
    - DO NOT schedule these during blocked_time_today windows.

  TIER 2 — Priority 2–3 (should do today, schedule in remaining free time):
    - Rolled-over tasks that are not optional.
    - New tasks generated from unactioned_emails or contacts_to_reach.
    - Respect free_minutes — if blocked time is heavy, keep tier 2 short.

  TIER 3 — Priority 4–5 (nice to do, include only if free_minutes allows):
    - Tasks from upcoming_due_dates where days_out >= 3 (start early, don't sprint).
    - Optional rolled tasks.
    - These go at the end of the list. Mark is_optional: true.

SCHEDULING RULES:
  - Never create a task that overlaps a window in blocked_time_today.
  - The sum of all task duration_minutes must not exceed free_minutes.
  - Total tasks: 3 minimum, 8 maximum. Fewer is better on heavy days.
  - Be realistic. A day with 4+ hours of blocked time should have 3–4 tasks max.
  - If there are no overdue/due-today tasks, lead with the most overdue rolled task.

OUTPUT FORMAT — respond with ONLY a JSON array, no explanation, no markdown, no backticks:
[
  {{
    "title": "Reply to recruiter email from Sarah Chen",
    "category": "network",
    "duration_minutes": 20,
    "priority": 1,
    "is_optional": false,
    "due_date": null,
    "notes": "Re: internship application follow-up"
  }}
]

Fields:
  title            — clear, specific action (not vague like "do homework")
  category         — one of: work, school, network, hobby, errand
  duration_minutes — realistic estimate
  priority         — 1 (tier 1) through 5 (tier 3 optional)
  is_optional      — true only for tier 3 tasks
  due_date         — ISO date string if this task has a real deadline, otherwise null
  notes            — one sentence of context, or null
""".strip()


# ─────────────────────────────────────────────
#  LLM CALL
#  Uses httpx instead of requests (avoids Windows connection issues with Ollama)
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

            # Strip markdown fences if the LLM ignored our instructions
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
#  If Ollama is down, surface what's already in the DB
#  in the same priority order the frontend expects.
# ─────────────────────────────────────────────

def _fallback_tasks() -> list[dict]:
    existing = task_svc.get_all()   # already ordered by the repo query
    pending  = [t for t in existing if t["status"] in ("pending", "rolled")]
    print(f"[planner] Using {len(pending)} fallback tasks from DB")
    return pending


# ─────────────────────────────────────────────
#  SAVE TASKS
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
                "due_date":          t.get("due_date"),       # ← LLM may supply this
                "source":            "planner",               # ← stamp provenance
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
            print(f"[planner] Saved task #{new_id} (priority {task['priority']}): '{task['title']}'")

        except Exception as e:
            print(f"[planner] Failed to save task '{t.get('title', '?')}': {e}")

    return saved


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _duration_minutes(start: str, end: str) -> int | None:
    """Parse two ISO datetime strings and return the gap in minutes."""
    try:
        fmt  = "%Y-%m-%dT%H:%M:%S"
        s    = datetime.fromisoformat(start)
        e    = datetime.fromisoformat(end)
        return int((e - s).total_seconds() / 60)
    except Exception:
        return None
def _seed_event_tasks(events_today: list[dict]) -> list[dict]:
    """
    For each calendar event today, check whether a task already exists for it
    (linked_event_id match). If not, create one.
 
    This is the bridge between calendar_events and tasks.
    These tasks are created with source='planner' and linked_event_id set,
    so we can detect duplicates on future syncs without scanning task titles.
 
    Returns the list of newly created tasks (may be empty if all already exist).
    """
    all_tasks    = task_svc.get_all()
    already_linked = {t["linked_event_id"] for t in all_tasks if t.get("linked_event_id")}
 
    seeded = []
 
    for event in events_today:
        event_id = event["id"]
 
        # Already has a task — skip
        if event_id in already_linked:
            continue
 
        event_type = event["event_type"]
        title      = event["title"]
        start      = event["start_time"]
        end        = event["end_time"]
        duration   = _duration_minutes(start, end) or 60
 
        # Map event type to task properties
        if event_type == "shift":
            category   = "work"
            priority   = 1
            is_optional = False
            task_title  = f"Work shift — {title}" if title.lower() not in ("work", "shift") else title
        elif event_type == "class":
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
            "due_date":          event["start_time"][:10],  # the event date IS the deadline
            "source":            "planner",
            "status":            "pending",
            "rolled_over_count": 0,
            "created_date":      date_.today().isoformat(),
            "linked_contact_id": event.get("linked_contact_id"),
            "linked_event_id":   event_id,   # ← the key link, prevents future duplicates
            "notes":             f"Calendar event: {start[11:16]}–{end[11:16]}" if end else None,
        }
 
        new_id     = task_svc.create(task)
        task["id"] = new_id
        seeded.append(task)
        print(f"[planner] Seeded task #{new_id} from calendar event '{title}'")
 
    return seeded

# ─────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def run_planner() -> list[dict]:
    """
    Execution order:
      1. Seed tasks from today's calendar events (deterministic, no LLM)
      2. Build context (the LLM sees event-sourced tasks as already pending)
      3. LLM fills in the rest — emails, contacts, rolled tasks
      4. Save LLM tasks, return everything
    """
    print(f"[planner] Running for {date_.today().isoformat()}...")
 
    # Step 1: calendar events → tasks (before LLM so it doesn't double-create)
    events_today = event_svc.get_today()
    seeded       = _seed_event_tasks(events_today)
    print(f"[planner] Seeded {len(seeded)} task(s) from calendar events")
 
    # Step 2–4: LLM handles everything else
    context   = _build_context()
    prompt    = _build_prompt(context)
    raw_tasks = _call_llm(prompt)
 
    if raw_tasks is None:
        return _fallback_tasks()
 
    llm_tasks = _save_tasks(raw_tasks)
 
    # Return seeded + LLM tasks together — repo ordering handles display sort
    return seeded + llm_tasks