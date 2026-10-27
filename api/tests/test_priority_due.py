"""우선순위 · 마감일 · 기한 초과 · 정렬 시나리오 (#19). 임시 DB에 alembic upgrade head 를 적용해 실행한다.

    uv run python -m unittest discover -s tests
"""
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from api import store
from api.main import app

API_DIR = Path(__file__).parents[1]

TODAY = date.today()
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()
LATER = (TODAY + timedelta(days=5)).isoformat()
LONG_AGO = (TODAY - timedelta(days=30)).isoformat()


def migrate(db: Path, target: str = "head") -> None:
    env = {**os.environ, "TASKFLOW_DB": str(db)}
    subprocess.run(["alembic", "upgrade", target], cwd=API_DIR, check=True, capture_output=True, env=env)


class TaskRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmp.name) / "rules.db"
        migrate(store.DB_PATH)
        cls._n = 0

    @classmethod
    def tearDownClass(cls) -> None:
        store.DB_PATH = cls._old_path
        cls._tmp.cleanup()

    def new_client(self) -> TestClient:
        type(self)._n += 1
        c = TestClient(app, base_url="http://localhost")
        cred = {"email": f"rules{self._n}@example.com", "password": "password-1"}
        self.assertEqual(c.post("/api/auth/signup", json=cred).status_code, 201)
        return c

    def make(self, c: TestClient, title: str, *, due=None, priority=None, status=None) -> dict:
        t = c.post("/api/tasks", json={"title": title}).json()
        body = {}
        if due is not None:
            body["due_date"] = due
        if priority is not None:
            body["priority"] = priority
        if body:
            t = c.patch(f"/api/tasks/{t['id']}", json=body).json()
        if status is not None:
            t = c.patch(f"/api/tasks/{t['id']}", json={"status": status}).json()
        return t

    def test_defaults(self) -> None:
        c = self.new_client()
        t = c.post("/api/tasks", json={"title": "기본"}).json()
        self.assertEqual(t["priority"], "NORMAL")
        self.assertIsNone(t["due_date"])
        self.assertIs(t["is_overdue"], False)
        self.assertEqual(c.post("/api/tasks", json={"title": "x", "priority": "HIGH"}).status_code, 422)
        self.assertEqual(c.post("/api/tasks", json={"title": "x", "due_date": TOMORROW}).status_code, 422)

    def test_overdue_table(self) -> None:
        # BUSINESS-RULES 5절: (마감일, 상태) -> 기한 초과
        cases = [
            (YESTERDAY, "todo", True),
            (YESTERDAY, "in_progress", True),
            (YESTERDAY, "done", False),
            (TODAY.isoformat(), "todo", False),
            (TODAY.isoformat(), "done", False),
            (TOMORROW, "todo", False),
            (TOMORROW, "done", False),
            (None, "todo", False),
            (None, "done", False),
        ]
        c = self.new_client()
        for due, status, expected in cases:
            with self.subTest(due=due, status=status):
                t = self.make(c, "표", due=due, status=None if status == "todo" else status)
                self.assertIs(t["is_overdue"], expected)  # 등록·수정·상태 변경 응답
                listed = next(x for x in c.get("/api/tasks").json() if x["id"] == t["id"])
                self.assertIs(listed["is_overdue"], expected)  # 목록 응답

    def test_overdue_changes_with_status_and_due_date(self) -> None:
        c = self.new_client()
        t = self.make(c, "초과", due=YESTERDAY)
        self.assertIs(t["is_overdue"], True)
        self.assertIs(c.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()["is_overdue"], False)
        self.assertIs(c.patch(f"/api/tasks/{t['id']}", json={"status": "todo"}).json()["is_overdue"], True)
        cleared = c.patch(f"/api/tasks/{t['id']}", json={"due_date": None}).json()
        self.assertIsNone(cleared["due_date"])
        self.assertIs(cleared["is_overdue"], False)

    def test_validation(self) -> None:
        c = self.new_client()
        t = self.make(c, "검증")
        url = f"/api/tasks/{t['id']}"
        self.assertEqual(c.patch(url, json={"priority": None}).status_code, 422)
        for bad in ("urgent", "low", "high", "MIDDLE", ""):
            self.assertEqual(c.patch(url, json={"priority": bad}).status_code, 422, bad)
        self.assertEqual(c.patch(url, json={"due_date": "내일"}).status_code, 422)
        self.assertEqual(c.patch(url, json={"due_date": f"{TOMORROW}T10:00:00"}).status_code, 422)
        self.assertEqual(c.patch(url, json={"status": "done", "priority": "HIGH"}).status_code, 422)
        self.assertEqual(c.get("/api/tasks").json()[0]["priority"], "NORMAL")  # 거절된 값은 저장되지 않는다
        r = c.patch(url, json={"due_date": LONG_AGO})  # 지난 날짜도 받는다
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["due_date"], LONG_AGO)

    def test_sort_order(self) -> None:
        c = self.new_client()
        # 일부러 정렬과 다른 순서(ID 순)로 만든다
        names = {}
        names["low_nodue"] = self.make(c, "low_nodue", priority="LOW")["id"]
        names["normal_nodue"] = self.make(c, "normal_nodue")["id"]
        names["normal_later"] = self.make(c, "normal_later", due=LATER)["id"]
        names["normal_tomorrow"] = self.make(c, "normal_tomorrow", due=TOMORROW)["id"]
        names["high_nodue"] = self.make(c, "high_nodue", priority="HIGH")["id"]
        names["high_later"] = self.make(c, "high_later", priority="HIGH", due=LATER)["id"]
        names["high_tomorrow"] = self.make(c, "high_tomorrow", priority="HIGH", due=TOMORROW)["id"]
        names["low_overdue"] = self.make(c, "low_overdue", priority="LOW", due=LONG_AGO)["id"]
        names["normal_overdue_old"] = self.make(c, "normal_overdue_old", due=LONG_AGO)["id"]
        names["normal_overdue_yesterday"] = self.make(c, "normal_overdue_yesterday", due=YESTERDAY)["id"]
        names["high_overdue"] = self.make(c, "high_overdue", priority="HIGH", due=YESTERDAY)["id"]
        names["done_old_high"] = self.make(c, "done_old_high", priority="HIGH", due=LONG_AGO, status="done")["id"]
        names["normal_nodue_2"] = self.make(c, "normal_nodue_2")["id"]

        expected = [
            "high_overdue",  # 기한 초과 먼저, 그 안에서 HIGH
            "normal_overdue_old",  # 같은 우선순위면 마감일이 이른 순
            "normal_overdue_yesterday",
            "low_overdue",
            "done_old_high",  # 완료라 기한 초과가 아니다. HIGH, 마감일 있음
            "high_tomorrow",
            "high_later",
            "high_nodue",  # 마감일 없음은 같은 우선순위 안에서 맨 뒤
            "normal_tomorrow",
            "normal_later",
            "normal_nodue",  # 같은 값이면 만든 순서(ID)
            "normal_nodue_2",
            "low_nodue",
        ]
        by_id = {v: k for k, v in names.items()}
        got = [by_id[t["id"]] for t in c.get("/api/tasks").json()]
        self.assertEqual(got, expected)

    def test_sort_keeps_values(self) -> None:
        c = self.new_client()
        a = self.make(c, "a", priority="LOW", due=TOMORROW)
        b = self.make(c, "b", priority="HIGH", due=YESTERDAY)
        by_id = {t["id"]: t for t in c.get("/api/tasks").json()}
        self.assertEqual(by_id[a["id"]], a)
        self.assertEqual(by_id[b["id"]], b)

    def test_only_my_tasks(self) -> None:
        a, b = self.new_client(), self.new_client()
        mine = self.make(a, "내 것", due=YESTERDAY)
        theirs = self.make(b, "남의 것", due=YESTERDAY)
        self.assertEqual([t["id"] for t in a.get("/api/tasks").json()], [mine["id"]])
        self.assertEqual(a.patch(f"/api/tasks/{theirs['id']}", json={"priority": "HIGH"}).status_code, 404)
        self.assertEqual(a.patch(f"/api/tasks/{theirs['id']}", json={"due_date": None}).status_code, 404)
        self.assertEqual(b.get("/api/tasks").json()[0]["priority"], "NORMAL")
        self.assertEqual(b.get("/api/tasks").json()[0]["due_date"], YESTERDAY)


class PriorityMigration(unittest.TestCase):
    def test_old_priority_values_are_mapped_and_rows_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "old.db"
            migrate(db, "0002")
            conn = sqlite3.connect(db)
            conn.execute("INSERT INTO users (email, password_hash) VALUES ('a@example.com', 'x'), ('b@example.com', 'x')")
            rows = [
                (1, "옛 low", "설명", "2026-10-21", "low", "done"),
                (2, "옛 normal", None, None, "normal", "todo"),
                (1, "옛 urgent", None, "2026-12-01", "urgent", "in_progress"),
            ]
            conn.executemany(
                "INSERT INTO tasks (owner_id, title, description, due_date, priority, status) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
            before = conn.execute("SELECT id, owner_id, title, description, due_date, status, created_at FROM tasks ORDER BY id").fetchall()
            conn.close()

            migrate(db)

            conn = sqlite3.connect(db)
            after = conn.execute("SELECT id, owner_id, title, description, due_date, status, created_at FROM tasks ORDER BY id").fetchall()
            self.assertEqual(after, before)  # priority 외 값과 행 수가 같다
            self.assertEqual(
                [r[0] for r in conn.execute("SELECT priority FROM tasks ORDER BY id")], ["LOW", "NORMAL", "HIGH"]
            )
            self.assertEqual(conn.execute("SELECT owner_id, count(*) FROM tasks GROUP BY owner_id ORDER BY owner_id").fetchall(), [(1, 2), (2, 1)])
            self.assertEqual(conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'tasks'").fetchone()[0], 3)
            self.assertIsNotNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'ix_tasks_owner_id'").fetchone())
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE tasks SET priority = 'urgent' WHERE id = 1")
            conn.execute("INSERT INTO tasks (owner_id, title) VALUES (1, '기본값')")
            self.assertEqual(conn.execute("SELECT priority FROM tasks WHERE title = '기본값'").fetchone()[0], "NORMAL")
            conn.close()


if __name__ == "__main__":
    unittest.main()
