from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


EVENT_NAMES = ("result_view", "cta_click")
CATEGORIES = ("love", "reconciliation", "compatibility", "work", "today")
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "analytics.sqlite3"


@dataclass(frozen=True)
class AnalyticsEvent:
    event_name: str
    category: str
    has_birthdate: bool
    session_id: str
    user_agent_hash: str | None = None


class AnalyticsStore:
    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL CHECK(event_name IN ('result_view', 'cta_click')),
                    category TEXT NOT NULL CHECK(category IN ('love', 'reconciliation', 'compatibility', 'work', 'today')),
                    has_birthdate INTEGER NOT NULL CHECK(has_birthdate IN (0, 1)),
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_agent_hash TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_name_category ON events(event_name, category)"
            )

    def record_event(self, event: AnalyticsEvent) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO events (
                    event_name, category, has_birthdate, created_at,
                    session_id, user_agent_hash
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_name,
                    event.category,
                    int(event.has_birthdate),
                    created_at,
                    event.session_id,
                    event.user_agent_hash,
                ),
            )

    def metrics(self) -> dict:
        counts = {
            category: {"result_view": 0, "cta_click": 0, "ctr_percent": 0.0}
            for category in CATEGORIES
        }
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT category, event_name, COUNT(*) AS count
                FROM events
                GROUP BY category, event_name
                """
            ).fetchall()

        for row in rows:
            counts[row["category"]][row["event_name"]] = row["count"]

        total_views = 0
        total_clicks = 0
        for category_counts in counts.values():
            views = category_counts["result_view"]
            clicks = category_counts["cta_click"]
            category_counts["ctr_percent"] = calculate_ctr(clicks, views)
            total_views += views
            total_clicks += clicks

        return {
            "overall": {
                "result_view": total_views,
                "cta_click": total_clicks,
                "ctr_percent": calculate_ctr(total_clicks, total_views),
            },
            "categories": counts,
        }


def calculate_ctr(clicks: int, views: int) -> float:
    if views <= 0:
        return 0.0
    return round(clicks / views * 100, 2)


def hash_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16]


def analytics_enabled() -> bool:
    load_dotenv()
    return os.getenv("ANALYTICS_ENABLED", "true").strip().lower() == "true"


def analytics_storage() -> str:
    load_dotenv()
    return os.getenv("ANALYTICS_STORAGE", "sqlite").strip().lower()
