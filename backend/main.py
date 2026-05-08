# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/tasks")
def get_tasks():
    # TODO (Phase 3): pull from MySQL
    return [{"id": 1, "title": "Test task", "category": "work", "duration": 60, "optional": False, "done": False}]