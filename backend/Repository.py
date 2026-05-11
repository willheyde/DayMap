from typing import Optional
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# ─────────────────────────────────────────────
#  CONNECTION
# ─────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(
        host     = os.getenv("DB_HOST", "127.0.0.1"),
        port     = os.getenv("DB_PORT", "8878"),
        user     = os.getenv("DB_USER", "postgres"),
        password = os.getenv("DB_PASS", "password"),
        dbname   = os.getenv("DB_NAME", "daymap"),
    )


# ─────────────────────────────────────────────
#  TASKS
# ─────────────────────────────────────────────

class TaskRepository:

    def get_all(self) -> list[dict]:
        """
        Returns active tasks in the order the frontend should display them:
 
          1. Overdue (due_date < today)          — priority 1 first, then oldest due date
          2. Due today (due_date = today)         — priority within that group
          3. Pending/rolled, no due date          — by priority, then how long they've been rolling
          4. Upcoming due dates (due_date > today)— soonest deadline first
          5. Optional tasks                       — last, regardless of anything else
 
        Dropped and completed tasks are excluded.
 
        CURRENT_DATE is passed in as a parameter so the query is testable
        and doesn't hardcode NOW() at the DB level.
        """
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM tasks
            WHERE status NOT IN ('dropped', 'complete')
            ORDER BY
                -- Optional tasks always go last
                is_optional ASC,
 
                -- Bucket 1: overdue (has a past due date)
                CASE
                    WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN 0
                    ELSE 1
                END ASC,
 
                -- Bucket 2: due today
                CASE
                    WHEN due_date = CURRENT_DATE THEN 0
                    ELSE 1
                END ASC,
 
                -- Bucket 3: future due date (soonest first within this bucket)
                CASE
                    WHEN due_date IS NOT NULL AND due_date > CURRENT_DATE THEN due_date
                    ELSE NULL
                END ASC NULLS LAST,
 
                -- Within each bucket, user-set priority wins
                priority ASC,
 
                -- Tiebreak: tasks that have been rolling longer surface first
                rolled_over_count DESC,
 
                -- Final tiebreak: oldest created first
                created_date ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_id(self, task_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, task: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks
                (title, category, status, duration_minutes, priority, is_optional,
                rolled_over_count, due_date, source, created_date,
                linked_contact_id, linked_event_id, notes)
            VALUES
                (%(title)s, %(category)s, %(status)s, %(duration_minutes)s, %(priority)s,
                %(is_optional)s, %(rolled_over_count)s, %(due_date)s, %(source)s,
                %(created_date)s, %(linked_contact_id)s, %(linked_event_id)s, %(notes)s)
            RETURNING id
        """, task)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, task_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [task_id]
        cursor.execute(f"UPDATE tasks SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, task_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# ─────────────────────────────────────────────
#  CONTACTS
# ─────────────────────────────────────────────

class ContactRepository:

    def get_all(self) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM contacts ORDER BY last_contacted DESC, name")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_id(self, contact_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_by_email(self, email: str) -> Optional[dict]:
        """Used by the email parser to match incoming mail to a known contact."""
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM contacts WHERE email = %s", (email,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, contact: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contacts
                (title, category, status, duration_minutes, priority, is_optional,
                rolled_over_count, due_date, source, created_date,
                linked_contact_id, linked_event_id, notes)
            VALUES
                (%(title)s, %(category)s, %(status)s, %(duration_minutes)s, %(priority)s,
                %(is_optional)s, %(rolled_over_count)s, %(due_date)s, %(source)s,
                %(created_date)s, %(linked_contact_id)s, %(linked_event_id)s, %(notes)s)
            RETURNING id
        """, contact)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, contact_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [contact_id]
        cursor.execute(f"UPDATE contacts SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, contact_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# ─────────────────────────────────────────────
#  EMAILS
# ─────────────────────────────────────────────

class EmailRepository:

    def get_all(self) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM emails ORDER BY received_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_unactioned(self) -> list[dict]:
        """Emails that require a follow-up and haven't been linked to a task yet."""
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM emails
            WHERE requires_action = TRUE AND linked_task_id IS NULL
            ORDER BY received_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_id(self, email_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM emails WHERE id = %s", (email_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, email: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emails
                (account, sender_name, sender_address, sender_contact_id, subject,
                 body_preview, received_at, is_read, requires_action, action_type,
                 linked_contact_id, linked_task_id)
            VALUES
                (%(account)s, %(sender_name)s, %(sender_address)s, %(sender_contact_id)s,
                 %(subject)s, %(body_preview)s, %(received_at)s, %(is_read)s,
                 %(requires_action)s, %(action_type)s, %(linked_contact_id)s, %(linked_task_id)s)
        """, email)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, email_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [email_id]
        cursor.execute(f"UPDATE emails SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, email_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails WHERE id = %s", (email_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# ─────────────────────────────────────────────
#  WORK SHIFTS  (deprecated — see CalendarEventRepository)
# ─────────────────────────────────────────────

class WorkShiftRepository:

    def get_all(self) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM work_shifts ORDER BY date DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_date(self, shift_date: str) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM work_shifts WHERE date = %s", (shift_date,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_by_id(self, shift_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM work_shifts WHERE id = %s", (shift_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, shift: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO work_shifts (date, start_time, end_time, location, notes)
            VALUES (%(date)s, %(start_time)s, %(end_time)s, %(location)s, %(notes)s)
        """, shift)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, shift_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [shift_id]
        cursor.execute(f"UPDATE work_shifts SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, shift_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM work_shifts WHERE id = %s", (shift_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# ─────────────────────────────────────────────
#  CALENDAR EVENTS
# ─────────────────────────────────────────────

class CalendarEventRepository:

    def get_all(self) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM calendar_events ORDER BY start_time")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_id(self, event_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM calendar_events WHERE id = %s", (event_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_by_date(self, event_date: str) -> list[dict]:
        """
        Returns all events whose start_time falls on the given date (YYYY-MM-DD).
        This is the query the planner calls first every morning.
        Results are ordered by start_time so the planner can walk through
        the day chronologically and find open scheduling windows.
        """
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM calendar_events
            WHERE DATE(start_time) = %s
            ORDER BY start_time
        """, (event_date,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_range(self, start: str, end: str) -> list[dict]:
        """
        Events with a start_time between two ISO datetime/date strings (inclusive).
        Used by the weekly view and lookahead scheduling.
        """
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM calendar_events
            WHERE start_time >= %s AND start_time <= %s
            ORDER BY start_time
        """, (start, end))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_ical_uid(self, ical_uid: str) -> Optional[dict]:
        """Dedup check before inserting an iCal import."""
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM calendar_events WHERE ical_uid = %s", (ical_uid,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, event: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calendar_events
                (title, event_type, start_time, end_time, location, notes,
                 is_recurring, linked_contact_id, ical_uid, gcal_id)
            VALUES
                (%(title)s, %(event_type)s, %(start_time)s, %(end_time)s,
                 %(location)s, %(notes)s, %(is_recurring)s,
                 %(linked_contact_id)s, %(ical_uid)s, %(gcal_id)s)
            RETURNING id
        """, event)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, event_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [event_id]
        cursor.execute(f"UPDATE calendar_events SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, event_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calendar_events WHERE id = %s", (event_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# ─────────────────────────────────────────────
#  DAY LOG
# ─────────────────────────────────────────────

class DayLogRepository:

    def get_all(self) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM day_logs ORDER BY date DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_by_date(self, log_date: str) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM day_logs WHERE date = %s", (log_date,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_by_id(self, log_id: int) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM day_logs WHERE id = %s", (log_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def create(self, log: dict) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO day_logs
                (date, start_time, end_time, tasks_completed, tasks_rolled_over,
                 tasks_dropped, notes)
            VALUES
                (%(date)s, %(start_time)s, %(end_time)s, %(tasks_completed)s,
                 %(tasks_rolled_over)s, %(tasks_dropped)s, %(notes)s)
            RETURNING id
        """, log)
        conn.commit()
        new_id = cursor.fetchone()[0]
        conn.close()
        return new_id

    def update(self, log_id: int, fields: dict) -> bool:
        if not fields:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        assignments = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [log_id]
        cursor.execute(f"UPDATE day_logs SET {assignments} WHERE id = %s", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete(self, log_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM day_logs WHERE id = %s", (log_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0