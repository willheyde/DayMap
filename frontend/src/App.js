import { useState, useEffect } from "react";
import "./App.css";

// ─── Task Categories ───────────────────────────────────────────────
// Inheritance-style approach in JS: a base task shape + category-specific config
// All tasks share the same structure; category drives icon, color, and sort weight

const CATEGORIES = {
  work:       { label: "Work",        icon: "◈", color: "var(--work)",    weight: 1 },
  school:     { label: "School",      icon: "◎", color: "var(--school)",  weight: 2 },
  network:    { label: "Network",     icon: "◇", color: "var(--network)", weight: 3 },
  hobby:      { label: "Hobby",       icon: "○", color: "var(--hobby)",   weight: 4 },
  errand:     { label: "Errand",      icon: "□", color: "var(--errand)",  weight: 5 },
};

// ─── Greeting Logic ─────────────────────────────────────────────────
// Mirrors the "night owl / early bird" vibe — driven by time of day + task progress
function getGreeting(completedCount, totalCount, hour) {
  const progress = totalCount === 0 ? 0 : completedCount / totalCount;

  if (hour >= 5  && hour < 9)  return progress < 0.1 ? "early riser. coffee first."        : "good start. keep it moving.";
  if (hour >= 9  && hour < 12) return progress < 0.3 ? "morning's slipping. get into it."  : "solid morning. stay locked.";
  if (hour >= 12 && hour < 15) return progress < 0.5 ? "afternoon. you've got time."       : "past halfway. don't coast.";
  if (hour >= 15 && hour < 18) return progress < 0.7 ? "late afternoon. push through."     : "almost there. finish strong.";
  if (hour >= 18 && hour < 22) return progress < 0.9 ? "evening grind. respect the work."  : "nearly done. wrap it up.";
  return progress >= 1         ? "all clear. rest earned."                                  : "night owl. whatever's left — tomorrow.";
}

// ─── Placeholder Data (replace with API call in Phase 3) ───────────
const MOCK_TASKS = [
  { id: 1, title: "Open shift at work",         category: "work",    duration: 240, optional: false, done: false },
  { id: 2, title: "Reach out to Jake @ Stripe", category: "network", duration: 15,  optional: false, done: false },
  { id: 3, title: "Push auth branch to GitHub", category: "school",  duration: 60,  optional: false, done: false },
  { id: 4, title: "Reply to Dr. Kim's email",   category: "school",  duration: 10,  optional: false, done: false },
  { id: 5, title: "Gym — upper body",            category: "hobby",   duration: 75,  optional: true,  done: false },
  { id: 6, title: "Grocery run",                 category: "errand",  duration: 30,  optional: true,  done: false },
];

// ─── Subcomponents ──────────────────────────────────────────────────

function TaskCard({ task, onToggle }) {
  const cat = CATEGORIES[task.category];
  return (
    <div
      className={`task-card ${task.done ? "done" : ""} ${task.optional ? "optional" : ""}`}
      onClick={() => onToggle(task.id)}
      style={{ "--cat-color": cat.color }}
    >
      <span className="task-icon">{cat.icon}</span>
      <div className="task-body">
        <span className="task-title">{task.title}</span>
        <span className="task-meta">
          {cat.label} · {task.duration}m{task.optional ? " · optional" : ""}
        </span>
      </div>
      <div className="task-check">{task.done ? "✕" : ""}</div>
    </div>
  );
}

function ProgressBar({ completed, total }) {
  const pct = total === 0 ? 0 : Math.round((completed / total) * 100);
  return (
    <div className="progress-wrap">
      <div className="progress-bar" style={{ width: `${pct}%` }} />
      <span className="progress-label">{completed}/{total} done</span>
    </div>
  );
}

function CategoryLegend() {
  return (
    <div className="legend">
      {Object.entries(CATEGORIES).map(([key, cat]) => (
        <span key={key} className="legend-item" style={{ color: cat.color }}>
          {cat.icon} {cat.label}
        </span>
      ))}
    </div>
  );
}

// ─── Main App ───────────────────────────────────────────────────────

export default function App() {
  const [tasks, setTasks]         = useState(MOCK_TASKS);
  const [dayActive, setDayActive] = useState(false);
  const [dayStart, setDayStart]   = useState(null);
  const [now, setNow]             = useState(new Date());

  // Clock tick — updates greeting + time display every minute
  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(tick);
  }, []);

  const completed = tasks.filter(t => t.done).length;
  const total     = tasks.length;
  const hour      = now.getHours();
  const greeting  = getGreeting(completed, total, hour);

  const timeString = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const dateString = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

  function toggleTask(id) {
    // TODO (Phase 3): PATCH /api/tasks/:id/toggle
    setTasks(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  }

  async function handleStartDay() {
  try {
    // 1. Make the actual network request
    // Note: FastAPI usually runs on port 8000 by default
    const response = await fetch("http://localhost:5000/api/tasks");
    
    if (!response.ok) throw new Error("Network response was not ok");

    const data = await response.json();
    
    // 2. Log the result to the browser console (F12 to view)
    console.log("Hello from the backend!", data);

    // 3. Update the UI state
    setDayStart(new Date());
    setDayActive(true);
    
    // Optional: If you want to replace mock tasks with backend tasks immediately:
    // setTasks(data);

  } catch (error) {
    console.error("CORS or Connection Error:", error);
  }
}

  function handleEndDay() {
    // TODO (Phase 3): POST /api/day/end — logs end timestamp, marks completed tasks, rolls over incomplete non-optionals
    setDayActive(false);
    setDayStart(null);
  }

  const sortedTasks = [...tasks].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1;
    return CATEGORIES[a.category].weight - CATEGORIES[b.category].weight;
  });

  const elapsed = dayStart
    ? Math.floor((now - dayStart) / 60_000)
    : null;

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <h1 className="logo">daymap</h1>
          <span className="greeting">{greeting}</span>
        </div>
        <div className="header-right">
          <span className="time">{timeString}</span>
          <span className="date">{dateString}</span>
        </div>
      </header>

      {/* ── Day Controls ── */}
      <div className="day-controls">
        {!dayActive ? (
          <button className="btn btn-start" onClick={handleStartDay}>
            start my day
          </button>
        ) : (
          <div className="day-active-row">
            <span className="elapsed">
              {Math.floor(elapsed / 60)}h {elapsed % 60}m into your day
            </span>
            <button className="btn btn-end" onClick={handleEndDay}>
              end my day
            </button>
          </div>
        )}
      </div>

      {/* ── Progress ── */}
      <ProgressBar completed={completed} total={total} />

      {/* ── Task List ── */}
      <main className="task-list">
        {sortedTasks.map(task => (
          <TaskCard key={task.id} task={task} onToggle={toggleTask} />
        ))}
      </main>

      {/* ── Footer Legend ── */}
      <footer className="footer">
        <CategoryLegend />
        {/* TODO (Phase 4): Add "check emails" indicator when unread signals exist */}
      </footer>
    </div>
  );
}