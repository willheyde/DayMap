from datetime import datetime, date as date_
from typing import Optional
from models import TaskStatus, TaskSource, ContactStatus, EventType
from Repository import (
    TaskRepository, ContactRepository, EmailRepository,
    WorkShiftRepository, DayLogRepository, CalendarEventRepository,
)

# ─────────────────────────────────────────────
#  MODULE-LEVEL REPO INSTANCES
#  One instance per repo, shared across all service classes in this process.
#  Services are instantiated in Controller.py — see the note there.
# ─────────────────────────────────────────────

task_repo     = TaskRepository()
contact_repo  = ContactRepository()
email_repo    = EmailRepository()
shift_repo    = WorkShiftRepository()
daylog_repo   = DayLogRepository()
event_repo    = CalendarEventRepository()   # ← new

ROLLOVER_DROP_THRESHOLD = 5


# ─────────────────────────────────────────────
#  TASK SERVICE
# ─────────────────────────────────────────────

class TaskService:

    def get_all(self) -> list[dict]:
        return task_repo.get_all()

    def get_by_id(self, task_id: int) -> Optional[dict]:
        return task_repo.get_by_id(task_id)

    def create(self, task: dict) -> int:
        task.setdefault("status",            TaskStatus.pending)
        task.setdefault("source",            TaskSource.manual)   # ← new
        task.setdefault("due_date",          None)                # ← new
        task.setdefault("rolled_over_count", 0)
        task.setdefault("created_date",      date_.today().isoformat())
        task.setdefault("is_optional",       False)
        task.setdefault("priority",          3)
        task.setdefault("linked_contact_id", None)
        task.setdefault("linked_event_id",   None)               # replaces linked_shift_id
        task.setdefault("notes",             None)
        return task_repo.create(task)

    def update(self, task_id: int, fields: dict) -> bool:
        return task_repo.update(task_id, fields)

    def delete(self, task_id: int) -> bool:
        return task_repo.delete(task_id)

    def complete(self, task_id: int) -> bool:
        return task_repo.update(task_id, {
            "status":         TaskStatus.complete,
            "completed_date": datetime.now().isoformat(),
        })

    def rollover_incomplete(self) -> dict:
        """
        Called at end-of-day.
        - Non-optional pending tasks → status=rolled, rolled_over_count++, source=rollover
        - Optional tasks past threshold → status=dropped
        Returns a summary dict for the DayLog.
        """
        tasks = task_repo.get_all()
        rolled  = []
        dropped = []

        for t in tasks:
            if t["status"] != TaskStatus.pending:
                continue

            if t["is_optional"] and t["rolled_over_count"] >= ROLLOVER_DROP_THRESHOLD:
                task_repo.update(t["id"], {"status": TaskStatus.dropped})
                dropped.append(t["id"])
            else:
                task_repo.update(t["id"], {
                    "status":            TaskStatus.rolled,
                    "source":            TaskSource.rollover,   # ← stamp provenance
                    "rolled_over_count": t["rolled_over_count"] + 1,
                })
                rolled.append(t["id"])

        return {"rolled": rolled, "dropped": dropped}


# ─────────────────────────────────────────────
#  CONTACT SERVICE
# ─────────────────────────────────────────────

class ContactService:

    def get_all(self) -> list[dict]:
        return contact_repo.get_all()

    def get_by_id(self, contact_id: int) -> Optional[dict]:
        return contact_repo.get_by_id(contact_id)

    def create(self, contact: dict) -> int:
        contact.setdefault("status", ContactStatus.target)
        return contact_repo.create(contact)

    def update(self, contact_id: int, fields: dict) -> bool:
        return contact_repo.update(contact_id, fields)

    def delete(self, contact_id: int) -> bool:
        return contact_repo.delete(contact_id)

    def log_interaction(self, contact_id: int, method: str, notes: Optional[str] = None) -> bool:
        contact = contact_repo.get_by_id(contact_id)
        if not contact:
            return False

        now = datetime.now().isoformat()
        updates: dict = {"last_contacted": now}

        if contact["status"] == ContactStatus.target:
            updates["status"] = ContactStatus.reached_out

        return contact_repo.update(contact_id, updates)

    def is_already_contacted(self, contact_id: int) -> bool:
        contact = contact_repo.get_by_id(contact_id)
        if not contact:
            return False
        return contact["last_contacted"] is not None

    def get_targets_for_today(self, limit: int = 3) -> list[dict]:
        all_contacts = contact_repo.get_all()
        targets = [c for c in all_contacts if c["status"] == ContactStatus.target]
        return targets[:limit]


# ─────────────────────────────────────────────
#  EMAIL SERVICE
# ─────────────────────────────────────────────

class EmailService:

    def get_all(self) -> list[dict]:
        return email_repo.get_all()

    def get_by_id(self, email_id: int) -> Optional[dict]:
        return email_repo.get_by_id(email_id)

    def get_unactioned(self) -> list[dict]:
        return email_repo.get_unactioned()

    def create(self, email: dict) -> int:
        match = contact_repo.get_by_email(email.get("sender_address", ""))
        if match:
            email["sender_contact_id"] = match["id"]
            email["linked_contact_id"] = match["id"]
        return email_repo.create(email)

    def update(self, email_id: int, fields: dict) -> bool:
        return email_repo.update(email_id, fields)

    def delete(self, email_id: int) -> bool:
        return email_repo.delete(email_id)

    def mark_read(self, email_id: int) -> bool:
        return email_repo.update(email_id, {"is_read": True})

    def link_to_task(self, email_id: int, task_id: int) -> bool:
        return email_repo.update(email_id, {"linked_task_id": task_id})


# ─────────────────────────────────────────────
#  WORK SHIFT SERVICE  (deprecated — keeping for now during migration)
# ─────────────────────────────────────────────

class WorkShiftService:

    def get_all(self) -> list[dict]:
        return shift_repo.get_all()

    def get_by_id(self, shift_id: int) -> Optional[dict]:
        return shift_repo.get_by_id(shift_id)

    def get_today(self) -> Optional[dict]:
        return shift_repo.get_by_date(date_.today().isoformat())

    def create(self, shift: dict) -> int:
        return shift_repo.create(shift)

    def update(self, shift_id: int, fields: dict) -> bool:
        return shift_repo.update(shift_id, fields)

    def delete(self, shift_id: int) -> bool:
        return shift_repo.delete(shift_id)


# ─────────────────────────────────────────────
#  CALENDAR EVENT SERVICE
# ─────────────────────────────────────────────

class CalendarEventService:

    def get_all(self) -> list[dict]:
        return event_repo.get_all()

    def get_by_id(self, event_id: int) -> Optional[dict]:
        return event_repo.get_by_id(event_id)

    def get_today(self) -> list[dict]:
        """
        The planner's first call. Returns today's events ordered by start_time
        so it can walk the day chronologically and find open scheduling windows.
        """
        return event_repo.get_by_date(date_.today().isoformat())

    def get_range(self, start: str, end: str) -> list[dict]:
        return event_repo.get_by_range(start, end)

    def create(self, event: dict) -> int:
        event.setdefault("event_type",        EventType.other)
        event.setdefault("is_recurring",      False)
        event.setdefault("location",          None)
        event.setdefault("notes",             None)
        event.setdefault("linked_contact_id", None)
        event.setdefault("ical_uid",          None)
        event.setdefault("gcal_id",           None)
        return event_repo.create(event)

    def update(self, event_id: int, fields: dict) -> bool:
        return event_repo.update(event_id, fields)

    def delete(self, event_id: int) -> bool:
        return event_repo.delete(event_id)

    def import_ical(self, ical_text: str) -> int:
        """
        Parses a raw .ics string and inserts events that don't already exist.

        Dedup key is  ical_uid:RECURRENCE-ID  (or just ical_uid for one-off events).
        This correctly handles recurring events — a MWF class has one base UID but
        a different RECURRENCE-ID per occurrence, so each day imports as its own row.

        Safe to call repeatedly with the same feed URL.
        Returns the count of newly inserted events.

        Requires: pip install icalendar
        """
        try:
            from icalendar import Calendar, vDatetime
        except ImportError:
            raise RuntimeError("icalendar package not installed. Run: pip install icalendar")

        cal      = Calendar.from_ical(ical_text)
        inserted = 0

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            base_uid     = str(component.get("uid", ""))
            recurrence_id = component.get("recurrence-id")

            # Build a composite key so recurring instances don't collide
            if recurrence_id:
                rec_str      = recurrence_id.dt.isoformat() if hasattr(recurrence_id, "dt") else str(recurrence_id)
                composite_uid = f"{base_uid}:{rec_str}"
            else:
                composite_uid = base_uid

            summary = str(component.get("summary", "Untitled"))
            dtstart = component.get("dtstart")
            dtend   = component.get("dtend")

            if not dtstart or not dtend:
                continue  # malformed — skip

            # Skip if this exact occurrence is already in the DB
            if composite_uid and event_repo.get_by_ical_uid(composite_uid):
                continue

            # Normalise date vs datetime (all-day events come back as date objects)
            start_dt = dtstart.dt
            end_dt   = dtend.dt
            if not hasattr(start_dt, "hour"):
                from datetime import datetime as dt_, time
                start_dt = dt_.combine(start_dt, time.min)
                end_dt   = dt_.combine(end_dt,   time.min)

            # Best-guess event_type from summary keywords
            lower = summary.lower()
            if any(w in lower for w in ("shift", "work")):
                event_type = EventType.shift
            elif any(w in lower for w in ("class", "lecture", "lab", "section", "course")):
                event_type = EventType.class_
            elif any(w in lower for w in ("meeting", "call", "chat", "sync", "interview")):
                event_type = EventType.meeting
            else:
                event_type = EventType.other

            self.create({
                "title":      summary,
                "event_type": event_type,
                "start_time": start_dt.isoformat(),
                "end_time":   end_dt.isoformat(),
                "ical_uid":   composite_uid or None,
                "location":   str(component.get("location", "") or ""),
                "notes":      str(component.get("description", "") or ""),
            })
            inserted += 1

        return inserted


# ─────────────────────────────────────────────
#  DAY LOG SERVICE
# ─────────────────────────────────────────────

class DayLogService:

    def get_all(self) -> list[dict]:
        return daylog_repo.get_all()

    def get_by_id(self, log_id: int) -> Optional[dict]:
        return daylog_repo.get_by_id(log_id)

    def get_today(self) -> Optional[dict]:
        return daylog_repo.get_by_date(date_.today().isoformat())

    def start_day(self) -> int:
        existing = self.get_today()
        if existing:
            return existing["id"]

        return daylog_repo.create({
            "date":              date_.today().isoformat(),
            "start_time":        datetime.now().isoformat(),
            "end_time":          None,
            "tasks_completed":   0,
            "tasks_rolled_over": 0,
            "tasks_dropped":     0,
            "notes":             None,
        })

    def end_day(self, log_id: int) -> bool:
        task_svc = TaskService()
        summary  = task_svc.rollover_incomplete()

        all_tasks       = task_repo.get_all()
        completed_count = sum(1 for t in all_tasks if t["status"] == TaskStatus.complete)

        return daylog_repo.update(log_id, {
            "end_time":          datetime.now().isoformat(),
            "tasks_completed":   completed_count,
            "tasks_rolled_over": len(summary["rolled"]),
            "tasks_dropped":     len(summary["dropped"]),
        })

    def update(self, log_id: int, fields: dict) -> bool:
        return daylog_repo.update(log_id, fields)

    def delete(self, log_id: int) -> bool:
        return daylog_repo.delete(log_id)