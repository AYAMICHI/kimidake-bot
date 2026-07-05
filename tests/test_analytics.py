import sqlite3
from contextlib import closing
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.kimidake_bot import web
from src.kimidake_bot.analytics import AnalyticsEvent, AnalyticsStore, hash_user_agent


class AnalyticsStoreTest(TestCase):
    def setUp(self):
        test_temp_root = Path.cwd() / ".pytest_tmp"
        test_temp_root.mkdir(exist_ok=True)
        self.database_path = test_temp_root / f"analytics-{uuid4().hex}.sqlite3"
        self.store = AnalyticsStore(self.database_path)

    def tearDown(self):
        self._remove_database_files()

    def _remove_database_files(self):
        for suffix in ("", "-shm", "-wal"):
            Path(f"{self.database_path}{suffix}").unlink(missing_ok=True)

    def test_metrics_calculate_overall_and_category_ctr(self):
        events = (
            AnalyticsEvent("result_view", "love", True, "anonymous-session-0001"),
            AnalyticsEvent("result_view", "love", False, "anonymous-session-0002"),
            AnalyticsEvent("cta_click", "love", True, "anonymous-session-0001"),
            AnalyticsEvent("result_view", "work", False, "anonymous-session-0003"),
        )
        for event in events:
            self.store.record_event(event)

        metrics = self.store.metrics()

        self.assertEqual(metrics["overall"]["result_view"], 3)
        self.assertEqual(metrics["overall"]["cta_click"], 1)
        self.assertEqual(metrics["overall"]["ctr_percent"], 33.33)
        self.assertEqual(metrics["categories"]["love"]["ctr_percent"], 50.0)
        self.assertEqual(metrics["categories"]["work"]["ctr_percent"], 0.0)

    def test_store_contains_only_anonymous_event_fields(self):
        raw_user_agent = "Test Browser/1.0"
        self.store.record_event(
            AnalyticsEvent(
                "result_view",
                "today",
                True,
                "anonymous-session-0004",
                hash_user_agent(raw_user_agent),
            )
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(events)").fetchall()
            }
            row = connection.execute("SELECT * FROM events").fetchone()

        self.assertEqual(
            columns,
            {
                "id",
                "event_name",
                "category",
                "has_birthdate",
                "created_at",
                "session_id",
                "user_agent_hash",
            },
        )
        self.assertNotIn(raw_user_agent, repr(row))
        self.assertNotIn("concern", columns)
        self.assertNotIn("result", columns)
        self.assertNotIn("birthday", columns)
        self.assertNotIn("nickname", columns)


class AnalyticsApiTest(TestCase):
    def setUp(self):
        test_temp_root = Path.cwd() / ".pytest_tmp"
        test_temp_root.mkdir(exist_ok=True)
        self.database_path = test_temp_root / f"analytics-{uuid4().hex}.sqlite3"
        self.store = AnalyticsStore(self.database_path)
        self.store_patch = patch(
            "src.kimidake_bot.web.get_analytics_store", return_value=self.store
        )
        self.store_patch.start()
        self.client = TestClient(web.app)

    def tearDown(self):
        self.store_patch.stop()
        for suffix in ("", "-shm", "-wal"):
            Path(f"{self.database_path}{suffix}").unlink(missing_ok=True)

    def post_event(self, event_name: str, category: str = "love"):
        return self.client.post(
            "/api/events",
            json={
                "event_name": event_name,
                "category": category,
                "has_birthdate": True,
                "session_id": "anonymous-session-12345",
            },
            headers={"User-Agent": "Raw Browser/9.9"},
        )

    def test_result_view_and_cta_click_are_saved(self):
        result_view = self.post_event("result_view", "reconciliation")
        cta_click = self.post_event("cta_click", "reconciliation")

        self.assertEqual(result_view.status_code, 200)
        self.assertEqual(result_view.json(), {"ok": True})
        self.assertEqual(cta_click.status_code, 200)
        metrics = self.store.metrics()["categories"]["reconciliation"]
        self.assertEqual(metrics["result_view"], 1)
        self.assertEqual(metrics["cta_click"], 1)

    def test_invalid_event_name_is_rejected(self):
        response = self.post_event("unknown_event")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.metrics()["overall"]["result_view"], 0)

    def test_invalid_category_is_rejected(self):
        response = self.post_event("result_view", "unknown")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.metrics()["overall"]["result_view"], 0)

    def test_sensitive_extra_fields_are_rejected_and_not_saved(self):
        response = self.client.post(
            "/api/events",
            json={
                "event_name": "result_view",
                "category": "work",
                "has_birthdate": True,
                "session_id": "anonymous-session-12345",
                "concern": "保存してはいけない悩み本文",
                "result": "保存してはいけないAI出力",
                "birthday": "2000-11-22",
                "nickname": "保存しない名前",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.metrics()["overall"]["result_view"], 0)
