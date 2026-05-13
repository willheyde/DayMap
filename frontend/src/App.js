import { useState, useEffect, useRef } from "react";
import "./App.css";

const CATEGORIES = {
  work:    { label: "Work",    icon: "◈", color: "var(--work)",    weight: 1 },
  school:  { label: "School",  icon: "◎", color: "var(--school)",  weight: 2 },
  network: { label: "Network", icon: "◇", color: "var(--network)", weight: 3 },
  hobby:   { label: "Hobby",   icon: "○", color: "var(--hobby)",   weight: 4 },
  errand:  { label: "Errand",  icon: "□", color: "var(--errand)",  weight: 5 },
};

const EVENT_ICONS = {
  shift:   "▣",
  class_:  "◉",
  meeting: "◫",
  other:   "◌",
};

const SOURCE_LABELS = {
  planner:  { label: "planned",  color: "var(--text-muted)" },
  email:    { label: "email",    color: "var(--school)"     },
  manual:   { label: "manual",   color: "var(--text-muted)" },
  rollover: { label: "rolled",   color: "var(--network)"    },
};

const API = "http://localhost:5000";

// ─── Helpers ─────────────────────────────────────────────────────────

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function dueDateMeta(dueDateRaw) {
  if (!dueDateRaw) return null;
  const due     = new Date(dueDateRaw + "T00:00:00");
  const today   = new Date(new Date().toDateString());
  const diffMs  = due - today;
  const diffDays = Math.round(diffMs / 86_400_000);

  if (diffDays < 0)  return { label: `${Math.abs(diffDays)}d overdue`, style: "overdue" };
  if (diffDays === 0) return { label: "due today",                       style: "today"   };
  if (diffDays === 1) return { label: "due tomorrow",                    style: "soon"    };
  if (diffDays <= 3)  return { label: `due in ${diffDays}d`,             style: "soon"    };
  return { label: due.toLocaleDateString([], { month: "short", day: "numeric" }), style: "future" };
}

function formatTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

// ─── Greeting ────────────────────────────────────────────────────────
function getGreeting(completedCount, totalCount, hour) {
  const progress = totalCount === 0 ? 0 : completedCount / totalCount;
  if (hour >= 5  && hour < 9)  return progress < 0.1 ? "early riser. coffee first."       : "good start. keep it moving.";
  if (hour >= 9  && hour < 12) return progress < 0.3 ? "morning's slipping. get into it." : "solid morning. stay locked.";
  if (hour >= 12 && hour < 15) return progress < 0.5 ? "afternoon. you've got time."      : "past halfway. don't coast.";
  if (hour >= 15 && hour < 18) return progress < 0.7 ? "late afternoon. push through."    : "almost there. finish strong.";
  if (hour >= 18 && hour < 22) return progress < 0.9 ? "evening grind. respect the work." : "nearly done. wrap it up.";
  return progress >= 1 ? "all clear. rest earned." : "night owl. whatever's left — tomorrow.";
}

// ─── Live Clock ──────────────────────────────────────────────────────
function LiveClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(tick);
  }, []);
  const hh   = String(now.getHours()).padStart(2, "0");
  const mm   = String(now.getMinutes()).padStart(2, "0");
  const ss   = String(now.getSeconds()).padStart(2, "0");
  const date = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  return (
    <div className="clock">
      <span className="clock-time">
        {hh}<span className="clock-colon">:</span>{mm}<span className="clock-seconds">{ss}</span>
      </span>
      <span className="clock-date">{date}</span>
    </div>
  );
}

// ─── Event Strip ─────────────────────────────────────────────────────
// Shows today's calendar events as a compact schedule strip above the task list.
function EventStrip({ events }) {
  if (!events || events.length === 0) return null;

  // Find the currently active event (if any)
  const now = new Date();

  return (
    <div className="event-strip">
      <span className="event-strip-label">today's schedule</span>
      <div className="event-list">
        {events.map(e => {
          const start   = new Date(e.start_time);
          const end     = e.end_time ? new Date(e.end_time) : null;
          const active  = now >= start && end && now <= end;
          const past    = end && now > end;
          const icon    = EVENT_ICONS[e.event_type] ?? EVENT_ICONS.other;

          return (
            <div
              key={e.id}
              className={`event-card ${active ? "active" : ""} ${past ? "past" : ""}`}
            >
              <span className="event-icon">{icon}</span>
              <div className="event-body">
                <span className="event-title">{e.title}</span>
                <span className="event-time">
                  {formatTime(e.start_time)}
                  {e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
                </span>
              </div>
              {active && <span className="event-now-badge">now</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Task Card ───────────────────────────────────────────────────────
function TaskCard({ task, onToggle, index }) {
  const cat     = CATEGORIES[task.category] ?? CATEGORIES.errand;
  const due     = dueDateMeta(task.due_date);
  const srcMeta = SOURCE_LABELS[task.source] ?? null;

  return (
    <div
      className={`task-card ${task.done ? "done" : ""} ${task.optional ? "optional" : ""}`}
      onClick={() => onToggle(task.id)}
      style={{ "--cat-color": cat.color, animationDelay: `${index * 60}ms` }}
    >
      <span className="task-icon">{cat.icon}</span>
      <div className="task-body">
        <span className="task-title">{task.title}</span>
        <div className="task-meta-row">
          <span className="task-meta">
            {cat.label}{task.duration ? ` · ${task.duration}m` : ""}{task.optional ? " · optional" : ""}
          </span>

          {/* Due date badge */}
          {due && (
            <span className={`due-badge due-${due.style}`}>{due.label}</span>
          )}

          {/* Source badge — only show non-manual, non-obvious ones */}
          {srcMeta && task.source !== "manual" && task.source !== "planner" && (
            <span className="source-badge" style={{ color: srcMeta.color }}>
              {srcMeta.label}
            </span>
          )}
        </div>
      </div>
      <div className={`task-check ${task.done ? "visible" : ""}`}>✕</div>
    </div>
  );
}

// ─── Progress Bar ────────────────────────────────────────────────────
function ProgressBar({ completed, total }) {
  const pct = total === 0 ? 0 : Math.round((completed / total) * 100);
  return (
    <div className="progress-wrap">
      <div className="progress-bar" style={{ width: `${pct}%` }} />
      <span className="progress-label">{completed}/{total} done</span>
    </div>
  );
}

// ─── Add Task Drawer ─────────────────────────────────────────────────
function AddTaskDrawer({ onAdd, onClose }) {
  const [step, setStep]         = useState("category");
  const [category, setCategory] = useState(null);
  const [title, setTitle]       = useState("");
  const [duration, setDuration] = useState("");
  const [dueDate, setDueDate]   = useState("");
  const [optional, setOptional] = useState(false);
  const [saving, setSaving]     = useState(false);
  const titleRef = useRef(null);

  useEffect(() => {
    if (step === "form") titleRef.current?.focus();
  }, [step]);

  function selectCategory(key) {
    setCategory(key);
    setStep("form");
  }

  async function handleSubmit() {
    if (!title.trim() || saving) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/tasks`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title:            title.trim(),
          category,
          duration_minutes: duration ? parseInt(duration) : 30,
          priority:         3,
          is_optional:      optional,
          due_date:         dueDate || null,
          source:           "manual",
        }),
      });
      const data = await res.json();
      onAdd({
        id:              data.id,
        title:           title.trim(),
        category,
        duration_minutes: duration ? parseInt(duration) : 30,
        is_optional:     optional,
        due_date:        dueDate || null,
        source:          "manual",
        status:          "pending",
      });
    } catch (e) {
      console.error("Failed to create task:", e);
    } finally {
      setSaving(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter")  handleSubmit();
    if (e.key === "Escape") step === "form" ? setStep("category") : onClose();
  }

  const cat = category ? CATEGORIES[category] : null;

  return (
    <div className="drawer">
      {step === "category" ? (
        <>
          <span className="drawer-label">what type of task?</span>
          <div className="cat-grid">
            {Object.entries(CATEGORIES).map(([key, c]) => (
              <button
                key={key}
                className="cat-option"
                style={{ "--cat-color": c.color }}
                onClick={() => selectCategory(key)}
              >
                <span className="cat-option-icon">{c.icon}</span>
                <span className="cat-option-label">{c.label}</span>
              </button>
            ))}
          </div>
          <div className="drawer-row">
            <span />
            <button className="btn btn-ghost" onClick={onClose}>cancel</button>
          </div>
        </>
      ) : (
        <>
          <div className="drawer-back" onClick={() => setStep("category")}>
            <span style={{ color: cat.color }}>{cat.icon} {cat.label}</span>
            <span className="back-label">← change</span>
          </div>
          <input
            ref={titleRef}
            className="drawer-input"
            placeholder="task name..."
            value={title}
            onChange={e => setTitle(e.target.value)}
            onKeyDown={handleKey}
            disabled={saving}
          />
          <div className="drawer-form-row">
            <div className="duration-wrap">
              <input
                className="drawer-input duration-input"
                type="number"
                placeholder="mins"
                min="1"
                value={duration}
                onChange={e => setDuration(e.target.value)}
                onKeyDown={handleKey}
                disabled={saving}
              />
            </div>
            {/* Due date picker — new */}
            <input
              className="drawer-input date-input"
              type="date"
              value={dueDate}
              min={todayStr()}
              onChange={e => setDueDate(e.target.value)}
              disabled={saving}
              title="due date (optional)"
            />
            <label className="optional-toggle">
              <input
                type="checkbox"
                checked={optional}
                onChange={e => setOptional(e.target.checked)}
              />
              <span>optional</span>
            </label>
            <div className="drawer-actions">
              <button className="btn btn-ghost" onClick={onClose}>cancel</button>
              <button
                className="btn btn-add"
                onClick={handleSubmit}
                disabled={saving || !title.trim()}
              >
                {saving ? "saving..." : "add"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
const STATUS_LABELS = {
  target:         { label: "not contacted", dim: false  },
  reached_out:    { label: "reached out",   dim: true   },
  waiting:        { label: "waiting",       dim: true   },
  replied:        { label: "replied",       dim: true   },
  met:            { label: "met",           dim: true   },
  not_interested: { label: "not interested",dim: true   },
};
function ContactCard({ contact, showStatus = false, onInteract = null }) {
  const [marking, setMarking] = useState(false);
  const status = STATUS_LABELS[contact.status] ?? STATUS_LABELS.target;
 
  async function handleInteract(e) {
    e.stopPropagation();
    if (marking) return;
    setMarking(true);
    try {
      await fetch(`${API}/api/contacts/${contact.id}/interact`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ method: "unknown" }),
      });
      onInteract?.(contact.id);
    } catch (err) {
      console.error("Failed to log interaction:", err);
    } finally {
      setMarking(false);
    }
  }
 
  return (
    <div className={`contact-card ${status.dim ? "contact-dim" : ""}`}>
      <div className="contact-body">
        <span className="contact-name">{contact.name}</span>
        {contact.company && (
          <span className="contact-company">{contact.company}</span>
        )}
        {showStatus && (
          <span className="contact-status">{status.label}</span>
        )}
      </div>
      <div className="contact-links">
        {contact.linkedin_url && (
          <a
            className="contact-link"
            href={contact.linkedin_url}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
          >
            in
          </a>
        )}
        {contact.email && (
          <a
            className="contact-link"
            href={`mailto:${contact.email}`}
            onClick={e => e.stopPropagation()}
          >
            @
          </a>
        )}
        {/* Only show "done" button on target contacts */}
        {onInteract && contact.status === "target" && (
          <button
            className="contact-link contact-done-btn"
            onClick={handleInteract}
            disabled={marking}
          >
            {marking ? "…" : "✓"}
          </button>
        )}
      </div>
    </div>
  );
}
 
 
// ─── ContactsSection ─────────────────────────────────────────────────
 
function ContactsSection({ contacts, onAdd, onInteract }) {
  const [open, setOpen]           = useState(false);
  const [showAll, setShowAll]     = useState(false);
  const [name, setName]           = useState("");
  const [company, setCompany]     = useState("");
  const [linkedin, setLinkedin]   = useState("");
  const [email, setEmail]         = useState("");
  const [saving, setSaving]       = useState(false);
  const nameRef = useRef(null);
 
  useEffect(() => {
    if (open) nameRef.current?.focus();
  }, [open]);
 
  // Split into daily targets vs the rest
  const targets    = contacts.filter(c => c.status === "target").slice(0, 3);
  const pipeline   = contacts.filter(c => c.status !== "target");
  const hasTargets = targets.length > 0;
 
  async function handleAdd() {
    if (!name.trim() || saving) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/contacts`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name:         name.trim(),
          company:      company.trim() || null,
          linkedin_url: linkedin.trim() || null,
          email:        email.trim() || null,
          status:       "target",
        }),
      });
      const data = await res.json();
      onAdd({
        id:           data.id,
        name:         name.trim(),
        company:      company.trim() || null,
        linkedin_url: linkedin.trim() || null,
        email:        email.trim() || null,
        status:       "target",
      });
      setName(""); setCompany(""); setLinkedin(""); setEmail("");
    } catch (e) {
      console.error("Failed to create contact:", e);
    } finally {
      setSaving(false);
    }
  }
 
  function handleKey(e) {
    if (e.key === "Enter")  handleAdd();
    if (e.key === "Escape") setOpen(false);
  }
 
  return (
    <div className="contacts-section">
 
      {/* ── Daily reach-out targets — always visible ───────────────── */}
      {hasTargets && (
        <div className="reach-out-strip">
          <span className="event-strip-label">
            reach out today · {targets.length} of 3
          </span>
          <div className="contact-list">
            {targets.map(c => (
              <ContactCard
                key={c.id}
                contact={c}
                onInteract={onInteract}
              />
            ))}
          </div>
        </div>
      )}
 
      {/* ── Full contacts panel — collapsible ─────────────────────── */}
      <div className="contacts-header" onClick={() => setOpen(v => !v)}>
        <span className="contacts-title">
          contacts
          {contacts.length > 0 && (
            <span className="contacts-count">{contacts.length}</span>
          )}
        </span>
        <span className="contacts-toggle">{open ? "−" : "+"}</span>
      </div>
 
      {open && (
        <div className="contacts-body">
 
          {/* Add form */}
          <div className="contact-form">
            <input
              ref={nameRef}
              className="drawer-input"
              placeholder="name"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={handleKey}
              disabled={saving}
            />
            <input
              className="drawer-input"
              placeholder="company"
              value={company}
              onChange={e => setCompany(e.target.value)}
              onKeyDown={handleKey}
              disabled={saving}
            />
            <input
              className="drawer-input"
              placeholder="linkedin url"
              value={linkedin}
              onChange={e => setLinkedin(e.target.value)}
              onKeyDown={handleKey}
              disabled={saving}
            />
            <input
              className="drawer-input"
              placeholder="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={handleKey}
              disabled={saving}
            />
            <div className="contact-form-actions">
              <button
                className="btn btn-add"
                onClick={handleAdd}
                disabled={saving || !name.trim()}
              >
                {saving ? "saving..." : "add contact"}
              </button>
            </div>
          </div>
 
          {/* Full list */}
          {contacts.length > 0 && (
            <>
              <div className="contact-list">
                {(showAll ? contacts : contacts.slice(0, 8)).map(c => (
                  <ContactCard
                    key={c.id}
                    contact={c}
                    showStatus
                    onInteract={c.status === "target" ? onInteract : null}
                  />
                ))}
              </div>
              {contacts.length > 8 && (
                <button
                  className="btn btn-ghost show-more-btn"
                  onClick={() => setShowAll(v => !v)}
                >
                  {showAll ? "show less" : `show all ${contacts.length}`}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
// ─── Main App ────────────────────────────────────────────────────────
export default function App() {
  const [tasks, setTasks]           = useState([]);
  const [events, setEvents]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [logId, setLogId]           = useState(null);
  const [dayActive, setDayActive]   = useState(false);
  const [dayStart, setDayStart]     = useState(null);
  const [now, setNow]               = useState(new Date());
  const [showDrawer, setShowDrawer] = useState(false);
  const [contacts, setContacts] = useState([]); 

  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    async function fetchTasks() {
      try {
        const res  = await fetch(`${API}/api/tasks`);
        const data = await res.json();
        setTasks(data.map(t => ({
          ...t,
          done:     t.status === "complete",
          optional: t.is_optional,
          duration: t.duration_minutes,
        })));
      } catch (e) {
        console.error("Failed to fetch tasks:", e);
      } finally {
        setLoading(false);
      }
    }
    async function fetchContacts() {
      try {
        const res  = await fetch(`${API}/api/contacts`);
        const data = await res.json();
        setContacts(data);
      } catch (e) { console.error("Failed to fetch contacts:", e); }
    }
    fetchContacts();
    async function fetchEvents() {
      try {
        const res  = await fetch(`${API}/api/events/today`);
        const data = await res.json();
        // Sort by start time ascending
        setEvents(data.sort((a, b) => new Date(a.start_time) - new Date(b.start_time)));
      } catch (e) {
        console.error("Failed to fetch events:", e);
      }
    }

    async function checkDayLog() {
      try {
        const res  = await fetch(`${API}/api/daylog/today`);
        const data = await res.json();
        if (data?.id && !data.end_time) {
          setLogId(data.id);
          setDayActive(true);
          setDayStart(new Date(data.start_time));
        }
      } catch (e) { console.error("Failed to check day log:", e); }
    }
    fetchTasks();
    fetchEvents();
    checkDayLog();
  }, []);

  const completed   = tasks.filter(t => t.done).length;
  const total       = tasks.length;
  const hour        = now.getHours();
  const greeting    = getGreeting(completed, total, hour);
  const elapsed     = dayStart ? Math.max(0, Math.floor((now - dayStart) / 60_000)) : null;
  const sortedTasks = [...tasks].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1;
    return (CATEGORIES[a.category]?.weight ?? 9) - (CATEGORIES[b.category]?.weight ?? 9);
  });

  async function toggleTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    const newDone = !task.done;
    setTasks(prev => prev.map(t => t.id === id ? { ...t, done: newDone } : t));
    try {
      await fetch(`${API}/api/tasks/${id}/complete`, { method: "PATCH" });
    } catch {
      setTasks(prev => prev.map(t => t.id === id ? { ...t, done: task.done } : t));
    }
  }

  async function handleStartDay() {
    try {
      const res  = await fetch(`${API}/api/daylog/start`, { method: "POST" });
      const data = await res.json();
      setLogId(data.log_id);
      setDayStart(new Date());
      setDayActive(true);
    } catch (e) { console.error("Failed to start day:", e); }
  }

  async function handleEndDay() {
    try {
      await fetch(`${API}/api/daylog/${logId}/end`, { method: "POST" });
      setDayActive(false);
      setDayStart(null);
      setLogId(null);
    } catch (e) { console.error("Failed to end day:", e); }
  }

  function handleTaskAdded(task) {
    setTasks(prev => [...prev, {
      ...task,
      done:     false,
      optional: task.is_optional ?? false,
      duration: task.duration_minutes ?? 30,
    }]);
  }
  function handleContactAdded(contact) {
     setContacts(prev => [contact, ...prev]);
  }
  function handleContactInteracted(contactId) {
    setContacts(prev =>
      prev.map(c =>
        c.id === contactId ? { ...c, status: "reached_out" } : c
      )
    );
  }
  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 className="logo">daymap</h1>
          <span className="greeting">{greeting}</span>
        </div>
        <LiveClock />
      </header>

      <div className="day-controls">
        <div className="day-controls-left">
          {!dayActive ? (
            <button className="btn btn-start" onClick={handleStartDay}>start my day</button>
          ) : (
            <div className="day-active-row">
              <span className="elapsed">{Math.floor(elapsed / 60)}h {elapsed % 60}m in</span>
              <button className="btn btn-end" onClick={handleEndDay}>end my day</button>
            </div>
          )}
        </div>
        <button className="btn btn-ghost btn-plus" onClick={() => setShowDrawer(v => !v)}>
          {showDrawer ? "✕" : "+ task"}
        </button>
      </div>

      {showDrawer && (
        <AddTaskDrawer
          onAdd={task => { handleTaskAdded(task); setShowDrawer(false); }}
          onClose={() => setShowDrawer(false)}
        />
      )}

      <ProgressBar completed={completed} total={total} />

      {/* Calendar events strip — sits between progress and task list */}
      <EventStrip events={events} />

      <main className="task-list">
        {loading ? (
          <span className="status-msg">fetching your day...</span>
        ) : tasks.length === 0 ? (
          <span className="status-msg">no tasks yet — run the planner to generate your day.</span>
        ) : (
          sortedTasks.map((task, i) => (
            <TaskCard key={task.id} task={task} onToggle={toggleTask} index={i} />
          ))
        )}
      </main>
       <ContactsSection contacts={contacts} onAdd={handleContactAdded} onInteract={handleContactInteracted} />
      <footer className="footer">
        <div className="legend">
          {Object.entries(CATEGORIES).map(([key, cat]) => (
            <span key={key} className="legend-item" style={{ color: cat.color }}>
              {cat.icon} {cat.label}
            </span>
          ))}
        </div>
      </footer>
    </div>
  );
}