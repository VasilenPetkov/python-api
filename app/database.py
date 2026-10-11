"""Small SQLite storage layer. Every operation uses its own connection."""

import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


@contextmanager
def connection():
    path = Path(os.getenv("DATABASE_PATH", "data/uptime.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as database:
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        with database:
            yield database


def initialize():
    with connection() as database:
        database.executescript("""
            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                expected_status INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY,
                monitor_id INTEGER NOT NULL REFERENCES monitors(id),
                checked_at TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms REAL NOT NULL,
                is_up INTEGER NOT NULL,
                error TEXT
            );
        """)
