# DayMap
# DayMap
### A personal daily planning agent built for real life

> Built by William Heyde — Summer 2025

---

## What Is This?

DayMap is a personal day-planning agent that wakes up before you do. Every morning, you open your computer, click **Start My Day**, and get a realistic, prioritized task list built from your actual life — your work schedule, your networking goals, your energy, and what you didn't finish yesterday.

No subscriptions. No cloud. Runs on your machine.

---

## The Core Idea

Most productivity apps ask you to manually input everything. DayMap inverts that. It pulls from your real data sources and generates your day for you. The goal isn't perfect optimization — it's showing up consistently, making progress on your internship search, and not burning out while working part-time.

The day starts when **you** say it does. DayMap plans around your actual schedule, not a fantasy 6am morning routine.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | JavaScript (Vanilla or React) | Displays the daily view, handles button interactions |
| Backend | Python (Flask or FastAPI) | Orchestrates logic, handles data sources |
| Database | MySQL | Stores tasks, contacts, completion history |
| AI / Planning | Ollama (local LLM — llama3 or mistral) | Runs entirely on your machine, zero cost, zero data leaving |
| Scheduler | Linux cron job | Regenerates the plan nightly between 3–5am |
| Email Parsing | Python IMAP (imaplib) | Reads Gmail/other accounts locally |

---

## How It Works

### The Daily Loop

```
[3-5am cron job runs]
        ↓
Backend pulls: work schedule + email + contacts list + yesterday's completion data
        ↓
Local LLM generates prioritized task list for the day
        ↓
Frontend displays the list — user clicks "Start My Day" when ready
        ↓
User works through the day
        ↓
User clicks "End My Day"
        ↓
Backend marks completions, carries over incomplete tasks, updates contact log
        ↓
[repeat]
```

### Wake/Sleep Window
When you click **Start My Day**, DayMap logs the timestamp. When you click **End My Day**, it logs that too. Over time it learns your actual active window and uses that to space tasks realistically throughout the day.

---

## Features

### Core (Build These First)
- **Daily task list** — generated every morning, displayed cleanly on load
- **Start / End Day buttons** — the only required user input
- **Task rollover** — incomplete tasks carry forward automatically
- **Contact deduplication** — a local log of every person contacted with timestamps, so you never accidentally double-message someone
- **Work schedule awareness** — blocks off work hours so tasks don't conflict

### Planned
- **Delinquency detection** — optional tasks (gym, hobby, side project) that haven't been touched in N days get quietly dropped, not nagged about
- **Email parsing** — scans both email accounts for relevant signals (replies, follow-ups needed, calendar invites)
- **Adaptive time allocation** — learns from your actual completion patterns over time to estimate how long things really take you

### Stretch Goals (If Time Allows)
- **Lock-in mode** — distraction blocking during focused work blocks
- **Weekly review summary** — a Friday EOD snapshot of networking progress, tasks completed, goals hit

---

## Data & Privacy

Everything runs locally. The LLM runs via Ollama on your machine. The database is a local MySQL instance. No data is sent to any external API unless you explicitly choose to connect one.

Credentials (email passwords, etc.) are stored in a local `.env` file that is **never committed to version control**.

```
# .env — never commit this
EMAIL_1_USER=you@gmail.com
EMAIL_1_PASS=your_app_password
EMAIL_2_USER=you@other.com
EMAIL_2_PASS=your_app_password
DB_HOST=localhost
DB_USER=root
DB_PASS=localpassword
```

---

## Database Schema (Draft)

```sql
-- The task list
tasks (
  id, title, category, estimated_minutes,
  priority, is_optional, status,
  created_date, completed_date, rolled_over_count
)

-- Everyone you've reached out to or plan to
contacts (
  id, name, platform, last_contacted_date,
  status, notes
)

-- Your active window history
day_log (
  id, start_time, end_time, date
)
```

---

## Project Structure (Planned)

```
daymap/
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── backend/
│   ├── main.py              # Flask/FastAPI entry point
│   ├── scheduler.py         # Cron-triggered nightly regen
│   ├── planner.py           # LLM prompt logic
│   ├── email_parser.py      # IMAP email reading
│   ├── task_manager.py      # Rollover, delinquency, completion logic
│   └── contact_tracker.py  # Contact log + deduplication
├── db/
│   └── schema.sql
├── .env                     # Never committed
├── .env.example             # Committed — shows required keys
├── requirements.txt
└── README.md
```

---

## Build Order

This is the order to build in — each phase is independently useful before moving to the next.

**Phase 1 — The Shell**
Get the frontend displaying a hardcoded task list. Build the Start/End Day buttons. Set up MySQL and the schema. Get Flask talking to the database.

**Phase 2 — The Brain**
Integrate Ollama locally. Feed it a manually-written JSON of your week and get it to return a reasonable task list. This is the proof of concept.

**Phase 3 — Real Data**
Hook up the work schedule (manual import or calendar sync). Build the contact tracker and rollover logic. Now the output is driven by real inputs.

**Phase 4 — Email**
IMAP parsing for both accounts. Focus on: do I need to follow up with anyone? Did someone reply to me? Is there a shift change?

**Phase 5 — Polish**
Delinquency detection, adaptive scheduling, UI cleanup, lock-in mode if you have time.

---

## Known Hard Problems

- **LinkedIn scraping** — LinkedIn actively blocks automated access. The workaround is maintaining your own contact list manually (export from LinkedIn once, keep it as a local JSON/DB table). DayMap helps you decide *who to contact today*, not find new people.
- **Work schedule parsing** — depends entirely on your employer's portal. Start with manual data entry, automate later if the portal exposes anything accessible.
- **Email noise** — most email is junk. The parser will need a filtering layer before it's useful signal.

---

## Goals This Summer

1. Land a software engineering internship
2. Network consistently without burning out
3. Build something real and ship it

---

*This README will be updated as the project evolves.*