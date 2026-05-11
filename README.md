# DayMap
### A personal daily planning agent built for real life

> Built by William Heyde — Summer 2025

---

## What Is This?

DayMap is a personal day-planning agent that wakes up before you do. Every morning, you open your computer, click **Start My Day**, and get a realistic, prioritized task list built from your actual life — your work schedule, your networking goals, your flagged emails, and what you didn't finish yesterday.

No subscriptions. No cloud. Runs entirely on your machine.

---

## The Core Idea

Most productivity apps ask you to manually input everything. DayMap inverts that. It pulls from your real data sources and generates your day for you. The goal isn't perfect optimization — it's showing up consistently, making progress on your internship search, and not burning out while working part-time.

The day starts when **you** say it does. DayMap plans around your actual schedule, not a fantasy 6am morning routine. Some days are a slog — work, meeting, reach out, work on a project. Some days are simple. The app reflects that without judgment.

**The 85% principle:** not all tasks are equal. A day where you crushed two hard deadlines but skipped the gym is a good day. DayMap is designed around that reality.

---

## Current Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React | Live clock, animated task cards, category drawer |
| Backend | Python + FastAPI + Uvicorn | REST API, runs on port 5000 |
| Database | PostgreSQL (pgAdmin4) | Local instance on port 8878 |
| AI / Planning | Ollama + llama3 | Runs fully local, zero API cost |
| Email Parsing | Python imaplib | Gmail via App Password, Outlook TBD |
| Scheduler | cron (planned) | Nightly 3–5am regen |

---

## How It Works

### The Daily Loop

```
[Nightly cron job OR manual trigger]
        ↓
email_parser.py scans Gmail for flagged emails (reply needed, follow-up, meeting)
        ↓
planner.py builds context: shift + flagged emails + contacts to reach + rolled tasks
        ↓
Local llama3 generates a prioritized task list (3–8 tasks, respects work hours)
        ↓
Tasks saved to PostgreSQL
        ↓
User opens app → clicks "Start My Day" → DayLog created with timestamp
        ↓
User works through the day, clicking tasks to complete them
        ↓
User clicks "End My Day" → rollover logic runs:
  - Incomplete non-optional tasks → status=rolled, rolled_over_count++
  - Optional tasks past threshold (5 days) → status=dropped
        ↓
[repeat]
```

---

## Project Structure

```
daymap/
├── frontend/
│   └── src/
│       ├── App.js           # Full React app — clock, task list, drawer, controls
│       └── App.css          # Dark theme, animations, category colors
├── backend/
│   ├── Controller.py        # FastAPI routes for all endpoints
│   ├── Service.py           # Business logic — rollover, dedup, delinquency
│   ├── Repository.py        # Raw PostgreSQL queries (psycopg2 + RealDictCursor)
│   ├── Models.py            # Pydantic models for all objects
│   ├── emailParser.py       # IMAP email fetching, parsing, action flagging
│   ├── planner.py           # LLM context builder + Ollama call + fallback
│   └── scheduler.py         # (planned) cron-triggered nightly run
├── db/
│   └── schema.sql           # Full PostgreSQL schema — run once in pgAdmin4
├── .env                     # Never committed
├── .env.example
├── requirements.txt
└── README.md
```

---

## Database Schema

```
tasks                — daily task list with rollover and delinquency tracking
contacts             — networking targets with status and interaction history
contact_interactions — one row per outreach / reply / meeting
emails               — parsed inbox items with action flags and contact linkage
work_shifts          — blocks off work hours so planner doesn't schedule over them
day_logs             — tracks start/end timestamps and EOD completion summary
```

Key design decisions:
- `rolled_over_count` on tasks drives delinquency detection — optional tasks dropped after 5 rolls
- Unique constraint on emails `(account, sender_address, received_at)` prevents duplicate imports
- `TEXT[]` on contacts tags enables `WHERE 'fintech' = ANY(tags)` queries later
- Foreign keys use `ON DELETE SET NULL` so deleting a contact doesn't cascade-delete tasks

---

## API Endpoints

```
GET    /api/tasks                   — all active tasks
POST   /api/tasks                   — create task (from drawer)
PATCH  /api/tasks/{id}/complete     — mark done
DELETE /api/tasks/{id}

GET    /api/contacts
POST   /api/contacts
POST   /api/contacts/{id}/interact  — log an outreach interaction
GET    /api/contacts/targets        — contacts ready to reach out to today

GET    /api/emails
GET    /api/emails/unactioned       — emails flagged as needing action
POST   /api/emails/sync             — triggers email_parser.run_email_sync()

POST   /api/daylog/start            — called by "Start My Day" button
POST   /api/daylog/{id}/end         — called by "End My Day", runs rollover
GET    /api/daylog/today

POST   /api/plan/generate           — triggers planner.run_planner()
```

---

## Frontend Features (Current)

- **Live clock** — ticks every second, colon blinks, seconds visible
- **Greeting** — changes based on time of day AND task completion progress
- **Task cards** — stagger in with animation, colored by category, click to complete
- **Progress bar** — glowing accent line, updates live as tasks are completed
- **Day state persistence** — page refresh mid-day restores active day log
- **Add task drawer** — two-step: pick category → enter name, duration, optional flag
- **Optimistic updates** — task flips instantly on click, syncs in background

### Task Categories
| Category | Use |
|---|---|
| Work | Shifts, work-related tasks |
| School | Classes, assignments, professor emails |
| Network | Reach outs, coffee chats, follow-ups |
| Hobby | Gym, side projects, optional activities |
| Errand | Grocery runs, appointments, admin |

---

## Environment Variables

```bash
# .env — never commit this file
DB_HOST=127.0.0.1
DB_PORT=8878
DB_USER=postgres
DB_PASS=yourpassword
DB_NAME=daymap

EMAIL1=you@ncsu.edu
EMAIL1PW=your_google_app_password   # 16-char App Password, not your real password
EMAIL2=you@outlook.com
EMAIL2PW=your_app_password

# Outlook note: Microsoft removed basic IMAP auth in 2024 — OAuth integration pending
```

---

## Known Issues & Decisions

- **Outlook IMAP** — Microsoft removed basic IMAP auth in 2024. OAuth integration is the fix, tabled for a future phase.
- **llama3 speed** — on CPU, Ollama responses take 2–5 minutes for a full planning prompt. GPU acceleration dramatically improves this. Timeout is set to 300s. Uses httpx (not requests) to avoid connection issues on Windows.
- **Hallucinated contacts** — if the contacts table is empty, the planner will invent placeholder people. Seed real contacts first.
- **JSON fencing** — local LLMs sometimes wrap responses in markdown fences despite instructions. The parser strips these before JSON.parse.
- **Port** — PostgreSQL is on 8878 (not the default 5432). The `DB_PORT` env var handles this.
- **psycopg2 cursors** — use `RealDictCursor` from `psycopg2.extras`, not `dictionary=True` (that's a MySQL-ism).

---

## Next Steps (Planned)

### Near term
- Add `due_date` and `source` fields to the tasks table — one migration, makes the planner significantly smarter
- **iCal import** — parse `.ics` exports from Google Calendar and Canvas into a `calendar_events` table so the planner knows what's blocking your day before scheduling anything

### Medium term
- **Weighted task scoring** — priority 1 tasks worth more points toward the 85% threshold so completing hard things counts more than skipping the gym
- **Background sync** — poll email + calendar every 30 minutes while the app is open, surface new urgent items automatically as new cards
- **Rewrite planner prompt** with calendar context — output should reflect your real blocked schedule, not just pending tasks

### Later
- **Google Calendar OAuth** — live event sync instead of manual iCal export
- **Outlook OAuth** — replace the broken IMAP approach
- **Weekly review** — Friday EOD snapshot of networking progress and tasks completed
- **Lock-in mode** — distraction blocking during focused work blocks

---

## Running Locally

```bash
# Backend
cd backend
pip install fastapi uvicorn psycopg2-binary python-dotenv httpx
uvicorn Controller:app --reload --port 5000

# Frontend
cd frontend
npm install
npm start

# Trigger a plan manually
python -c "from planner import run_planner; run_planner()"

# Trigger email sync manually
python -c "from emailParser import run_email_sync; run_email_sync()"

# Ollama must be running separately
ollama serve

---

*Last updated: May 2026*
