"""Uptime monitoring API: register URLs, check them, and read their history."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

from app.database import connection, initialize


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield


app = FastAPI(title="Uptime Monitor API", version="0.1.0", lifespan=lifespan)


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    expected_status: int = Field(default=200, ge=100, le=599)


class Monitor(BaseModel):
    id: int
    name: str
    url: str
    expected_status: int


class Check(BaseModel):
    id: int
    monitor_id: int
    checked_at: datetime
    status_code: int | None
    response_time_ms: float
    is_up: bool
    error: str | None


def find_monitor(monitor_id: int):
    with connection() as database:
        monitor = database.execute(
            "SELECT * FROM monitors WHERE id = ?", (monitor_id,)
        ).fetchone()
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return dict(monitor)


@app.get("/health")
def health():
    with connection() as database:
        database.execute("SELECT id FROM monitors LIMIT 1").fetchone()
    return {"status": "ok"}


@app.post("/monitors", response_model=Monitor, status_code=201)
def create_monitor(monitor: MonitorCreate):
    with connection() as database:
        cursor = database.execute(
            "INSERT INTO monitors (name, url, expected_status) VALUES (?, ?, ?)",
            (monitor.name, str(monitor.url), monitor.expected_status),
        )
        monitor_id = cursor.lastrowid
    return find_monitor(monitor_id)


@app.get("/monitors", response_model=list[Monitor])
def list_monitors():
    with connection() as database:
        rows = database.execute("SELECT * FROM monitors ORDER BY id").fetchall()
    return [dict(row) for row in rows]


@app.get("/monitors/{monitor_id}", response_model=Monitor)
def get_monitor(monitor_id: int):
    return find_monitor(monitor_id)


@app.post("/monitors/{monitor_id}/checks", response_model=Check, status_code=201)
def run_check(monitor_id: int):
    monitor = find_monitor(monitor_id)
    checked_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    status_code = None
    error = None
    try:
        # Bound connection/read waits; do not follow redirects or download bodies.
        with httpx.stream("GET", monitor["url"], timeout=5.0, follow_redirects=False) as response:
            status_code = response.status_code
    except httpx.RequestError as exc:
        error = type(exc).__name__
    response_time_ms = round((perf_counter() - started) * 1000, 2)
    is_up = status_code == monitor["expected_status"]
    with connection() as database:
        cursor = database.execute(
            """INSERT INTO checks
               (monitor_id, checked_at, status_code, response_time_ms, is_up, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (monitor_id, checked_at, status_code, response_time_ms, is_up, error),
        )
        row = database.execute("SELECT * FROM checks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.get("/monitors/{monitor_id}/checks", response_model=list[Check])
def list_checks(monitor_id: int, limit: int = Query(default=50, ge=1, le=500)):
    find_monitor(monitor_id)
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM checks WHERE monitor_id = ? ORDER BY id DESC LIMIT ?",
            (monitor_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
