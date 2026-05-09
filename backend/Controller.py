from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from Service import TaskService, ContactService, EmailService, WorkShiftService, DayLogService
from backend.emailParser import run_email_sync

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

task_svc     = TaskService()
contact_svc  = ContactService()
email_svc    = EmailService()
shift_svc    = WorkShiftService()
daylog_svc   = DayLogService()


# ─────────────────────────────────────────────
#  TASKS
# ─────────────────────────────────────────────

@app.get("/api/tasks")
def get_tasks():
    return task_svc.get_all()

@app.get("/api/tasks/{task_id}")
def get_task(task_id: int):
    task = task_svc.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks", status_code=201)
def create_task(task: dict):
    new_id = task_svc.create(task)
    return {"id": new_id}

@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, fields: dict):
    updated = task_svc.update(task_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}

@app.patch("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    completed = task_svc.complete(task_id)
    if not completed:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    deleted = task_svc.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


# ─────────────────────────────────────────────
#  CONTACTS
# ─────────────────────────────────────────────

@app.get("/api/contacts")
def get_contacts():
    return contact_svc.get_all()

@app.get("/api/contacts/targets")
def get_contact_targets():
    """Returns contacts ready to be reached out to today."""
    return contact_svc.get_targets_for_today()

@app.get("/api/contacts/{contact_id}")
def get_contact(contact_id: int):
    contact = contact_svc.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@app.post("/api/contacts", status_code=201)
def create_contact(contact: dict):
    new_id = contact_svc.create(contact)
    return {"id": new_id}

@app.patch("/api/contacts/{contact_id}")
def update_contact(contact_id: int, fields: dict):
    updated = contact_svc.update(contact_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}

@app.post("/api/contacts/{contact_id}/interact")
def log_interaction(contact_id: int, body: dict):
    """Log that you reached out — method and optional notes in body."""
    ok = contact_svc.log_interaction(
        contact_id,
        method=body.get("method", "unknown"),
        notes=body.get("notes"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}

@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int):
    deleted = contact_svc.delete(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}


# ─────────────────────────────────────────────
#  EMAILS
# ─────────────────────────────────────────────

@app.get("/api/emails")
def get_emails():
    return email_svc.get_all()

@app.get("/api/emails/unactioned")
def get_unactioned_emails():
    return email_svc.get_unactioned()

@app.get("/api/emails/{email_id}")
def get_email(email_id: int):
    email = email_svc.get_by_id(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email

@app.post("/api/emails", status_code=201)
def create_email(email: dict):
    new_id = email_svc.create(email)
    return {"id": new_id}

@app.patch("/api/emails/{email_id}")
def update_email(email_id: int, fields: dict):
    updated = email_svc.update(email_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"ok": True}

@app.patch("/api/emails/{email_id}/read")
def mark_email_read(email_id: int):
    email_svc.mark_read(email_id)
    return {"ok": True}

@app.patch("/api/emails/{email_id}/link/{task_id}")
def link_email_to_task(email_id: int, task_id: int):
    email_svc.link_to_task(email_id, task_id)
    return {"ok": True}

@app.delete("/api/emails/{email_id}")
def delete_email(email_id: int):
    deleted = email_svc.delete(email_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"ok": True}
@app.post("/api/emails/sync")
def sync_emails():
    summary = run_email_sync()
    return summary

# ─────────────────────────────────────────────
#  WORK SHIFTS
# ─────────────────────────────────────────────

@app.get("/api/shifts")
def get_shifts():
    return shift_svc.get_all()

@app.get("/api/shifts/today")
def get_todays_shift():
    shift = shift_svc.get_today()
    if not shift:
        return {"shift": None}
    return shift

@app.get("/api/shifts/{shift_id}")
def get_shift(shift_id: int):
    shift = shift_svc.get_by_id(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift

@app.post("/api/shifts", status_code=201)
def create_shift(shift: dict):
    new_id = shift_svc.create(shift)
    return {"id": new_id}

@app.patch("/api/shifts/{shift_id}")
def update_shift(shift_id: int, fields: dict):
    updated = shift_svc.update(shift_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Shift not found")
    return {"ok": True}

@app.delete("/api/shifts/{shift_id}")
def delete_shift(shift_id: int):
    deleted = shift_svc.delete(shift_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Shift not found")
    return {"ok": True}


# ─────────────────────────────────────────────
#  DAY LOG
# ─────────────────────────────────────────────

@app.get("/api/daylog")
def get_day_logs():
    return daylog_svc.get_all()

@app.get("/api/daylog/today")
def get_today_log():
    log = daylog_svc.get_today()
    if not log:
        return {"log": None}
    return log

@app.get("/api/daylog/{log_id}")
def get_day_log(log_id: int):
    log = daylog_svc.get_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Day log not found")
    return log

@app.post("/api/daylog/start")
def start_day():
    """Called when the user clicks 'Start My Day'."""
    log_id = daylog_svc.start_day()
    return {"log_id": log_id}

@app.post("/api/daylog/{log_id}/end")
def end_day(log_id: int):
    """Called when the user clicks 'End My Day'. Runs rollover logic."""
    ok = daylog_svc.end_day(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Day log not found")
    return {"ok": True}

@app.delete("/api/daylog/{log_id}")
def delete_day_log(log_id: int):
    deleted = daylog_svc.delete(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Day log not found")
    return {"ok": True}