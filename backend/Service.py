from datetime import datetime, date as date_
from typing import Optional
from models import TaskStatus, ContactStatus
from Repository import (
    TaskRepository, ContactRepository,
    EmailRepository, WorkShiftRepository, DayLogRepository
)

task_repo     = TaskRepository()
contact_repo  = ContactRepository()
email_repo    = EmailRepository()
shift_repo    = WorkShiftRepository()
daylog_repo   = DayLogRepository()

ROLLOVER_DROP_THRESHOLD = 5  # days before an optional task gets auto-dropped


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
        task.setdefault("rolled_over_count", 0)
        task.setdefault("created_date",      date_.today().isoformat())
        task.setdefault("is_optional",       False)
        task.setdefault("priority",          3)
        return task_repo.create(task)

    def update(self, task_id: int, fields: dict) -> bool:
        return task_repo.update(task_id, fields)

    def delete(self, task_id: int) -> bool:
        return task_repo.delete(task_id)

    def complete(self, task_id: int) -> bool:
        """Mark a task done and stamp the completion time."""
        return task_repo.update(task_id, {
            "status":         TaskStatus.complete,
            "completed_date": datetime.now().isoformat(),
        })

    def rollover_incomplete(self) -> dict:
        """
        Called at end-of-day.
        - Non-optional incomplete tasks → status=rolled, rolled_over_count++
        - Optional tasks past threshold  → status=dropped
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
        """
        Record that you reached out or heard back from someone.
        Updates last_contacted and bumps status if still at 'target'.
        """
        contact = contact_repo.get_by_id(contact_id)
        if not contact:
            return False

        now = datetime.now().isoformat()
        updates: dict = {"last_contacted": now}

        if contact["status"] == ContactStatus.target:
            updates["status"] = ContactStatus.reached_out

        # TODO (Phase 4): also insert a row into contact_interactions table
        return contact_repo.update(contact_id, updates)

    def is_already_contacted(self, contact_id: int) -> bool:
        """Dedup guard — returns True if we've ever reached out."""
        contact = contact_repo.get_by_id(contact_id)
        if not contact:
            return False
        return contact["last_contacted"] is not None

    def get_targets_for_today(self, limit: int = 3) -> list[dict]:
        """
        Returns contacts we haven't yet reached out to, ordered by source priority.
        Used by the planner to generate networking tasks.
        TODO (Phase 3): weight this by recency, company relevance, mutual connections, etc.
        """
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
        # try to auto-link sender to a known contact
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
#  WORK SHIFT SERVICE
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
        """Creates a new DayLog entry stamped with the current time."""
        existing = self.get_today()
        if existing:
            return existing["id"]   # idempotent — don't double-log the same day

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
        """
        Stamps end time and runs the rollover logic.
        Called when the user clicks 'End My Day'.
        """
        task_svc = TaskService()
        summary  = task_svc.rollover_incomplete()

        all_tasks     = task_repo.get_all()
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