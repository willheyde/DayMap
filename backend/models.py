from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date as date_, time
from enum import Enum


# ─────────────────────────────────────────────
#  ENUMS
# ─────────────────────────────────────────────

class TaskCategory(str, Enum):
    work    = "work"
    school  = "school"
    network = "network"
    hobby   = "hobby"
    errand  = "errand"

class TaskStatus(str, Enum):
    pending   = "pending"
    complete  = "complete"
    rolled    = "rolled"    # carried over from a previous day
    dropped   = "dropped"   # optional task removed after delinquency threshold

class ContactStatus(str, Enum):
    target        = "target"       # identified, not yet reached out
    reached_out   = "reached_out"  # message sent, no reply
    waiting       = "waiting"      # follow-up sent, still waiting
    replied       = "replied"      # they responded
    met           = "met"          # had a real conversation / coffee chat
    not_interested = "not_interested"

class EmailActionType(str, Enum):
    reply_needed    = "reply_needed"
    follow_up       = "follow_up"
    schedule_meeting = "schedule_meeting"
    none            = "none"


# ─────────────────────────────────────────────
#  INNER OBJECTS
# ─────────────────────────────────────────────

class EmailSender(BaseModel):
    """Who sent the email — broken out so we can cross-reference against contacts"""
    name:    Optional[str]  = None
    address: str                        # raw email address
    contact_id: Optional[int] = None    # FK → Contact.id if we recognize them


class TimeWindow(BaseModel):
    """A start/end time pair — reused across WorkShift and DayLog"""
    start: datetime
    end:   Optional[datetime] = None    # None means still in progress

    @property
    def duration_minutes(self) -> Optional[int]:
        if self.end is None:
            return None
        return int((self.end - self.start).total_seconds() / 60)


class ContactHistory(BaseModel):
    """A single interaction with a contact — stored as a list on Contact"""
    date:     datetime
    method:   str           # "email" | "linkedin" | "text" | "call" | "in_person"
    notes:    Optional[str] = None
    task_id:  Optional[int] = None  # FK → Task.id if this came from a task


# ─────────────────────────────────────────────
#  CORE MODELS
# ─────────────────────────────────────────────

class Task(BaseModel):
    id:               Optional[int]   = None
    title:            str
    category:         TaskCategory
    status:           TaskStatus      = TaskStatus.pending
    duration_minutes: int             = 30
    priority:         int             = 3             # 1 (highest) → 5 (lowest)
    is_optional:      bool            = False
    rolled_over_count: int            = 0             # how many days this has been carried
    created_date:     date_           = Field(default_factory=date_.today)
    completed_date:   Optional[datetime] = None

    # optional linkage
    linked_contact_id: Optional[int] = None   # FK → Contact.id  (e.g. "reach out to Jake")
    linked_shift_id:   Optional[int] = None   # FK → WorkShift.id (e.g. "open shift")
    notes:             Optional[str] = None


class Contact(BaseModel):
    id:               Optional[int]  = None
    name:             str
    company:          Optional[str]  = None
    role:             Optional[str]  = None
    status:           ContactStatus  = ContactStatus.target

    # ways to reach them
    email:            Optional[str]  = None
    linkedin_url:     Optional[str]  = None
    phone:            Optional[str]  = None

    # context
    source:           Optional[str]  = None   # "linkedin" | "referral" | "event" | "cold"
    notes:            Optional[str]  = None
    tags:             list[str]      = []      # e.g. ["fintech", "swe", "alumni"]

    # history — each element is a ContactHistory object
    interactions:     list[ContactHistory] = []

    # dedup guard — last_contacted is derived from interactions but cached here
    last_contacted:   Optional[datetime]   = None

    @property
    def times_contacted(self) -> int:
        return len(self.interactions)


class Email(BaseModel):
    id:           Optional[int]  = None
    account:      str            # which inbox — e.g. "personal" | "school"
    sender:       EmailSender
    subject:      str
    body_preview: Optional[str]  = None   # first ~200 chars, not the full body
    received_at:  datetime

    is_read:          bool = False
    requires_action:  bool = False
    action_type:      EmailActionType = EmailActionType.none

    # linkage — did we figure out who/what this relates to?
    linked_contact_id: Optional[int] = None   # FK → Contact.id
    linked_task_id:    Optional[int] = None   # FK → Task.id


class WorkShift(BaseModel):
    id:       Optional[int] = None
    date:     date_
    window:   TimeWindow
    location: Optional[str] = None
    notes:    Optional[str] = None

    @property
    def duration_minutes(self) -> Optional[int]:
        return self.window.duration_minutes


class DayLog(BaseModel):
    id:     Optional[int] = None
    date:   date_          = Field(default_factory=date_.today)
    window: TimeWindow

    # snapshot at EOD
    tasks_completed:   int       = 0
    tasks_rolled_over: int       = 0
    tasks_dropped:     int       = 0

    # the raw list of task IDs touched today
    completed_task_ids:    list[int] = []
    rolled_over_task_ids:  list[int] = []

    notes: Optional[str] = None   # freeform EOD note, could be useful later for ML