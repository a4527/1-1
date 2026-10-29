"""DB에 규칙 밖 마감일(YYYY-MM-DD 실제 날짜가 아닌 값)이 있어도 보드와 계획이 깨지지 않는다.

    uv run python -m unittest discover -s tests
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from api import store
from api.main import app

API_DIR = Path(__file__).parents[1]
BAD_DUES = ["다음주", "2026-1-5", "2026-02-30", "2026/10/01", ""]


class DueRead(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmp.name) / "due_read.db"
        env = {**os.environ, "TASKFLOW_DB": str(store.DB_PATH)}
        subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True, env=env)
        cls.client = TestClient(app, base_url="http://localhost")
        cred = {"email": "due-read@example.com", "password": "password-1"}
        assert cls.client.post("/api/auth/signup", json=cred).status_code == 201
        cls.ids = [cls.client.post("/api/tasks", json={"title": f"규칙 밖 {v!r}"}).json()["id"] for v in BAD_DUES]
        cls.good = cls.client.post("/api/tasks", json={"title": "정상"}).json()["id"]
        with sqlite3.connect(store.DB_PATH) as conn:  # API를 거치지 않고 DB에 바로 넣는다
            conn.executemany("UPDATE tasks SET due_date = ? WHERE id = ?", zip(BAD_DUES, cls.ids))
            conn.execute("UPDATE tasks SET due_date = '2000-01-01' WHERE id = ?", (cls.good,))

    @classmethod
    def tearDownClass(cls) -> None:
        store.DB_PATH = cls._old_path
        cls._tmp.cleanup()

    def test_board_reads_bad_due_as_none(self) -> None:
        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 200)
        tasks = {t["id"]: t for t in res.json()}
        for task_id, value in zip(self.ids, BAD_DUES):
            with self.subTest(due=value):
                self.assertIsNone(tasks[task_id]["due_date"])
                self.assertFalse(tasks[task_id]["is_overdue"])
        self.assertEqual(res.json()[0]["id"], self.good)  # 진짜 기한 초과만 맨 앞
        self.assertTrue(tasks[self.good]["is_overdue"])

    def test_weekplan_with_bad_due(self) -> None:
        create = mock.Mock(
            return_value=SimpleNamespace(
                stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"days": [], "note": "n"}')]
            )
        )
        fake = mock.Mock()
        fake.messages.create = create
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), mock.patch(
            "api.suggest.anthropic.Anthropic", return_value=fake
        ):
            res = self.client.post("/api/tasks/weekplan")
        self.assertEqual(res.status_code, 200)
        placed = [i for d in res.json()["days"] for i in d["ids"]]
        self.assertEqual(sorted(placed), sorted([*self.ids, self.good]))  # 모두 표에 들어간다
        sent = json.loads(create.call_args.kwargs["messages"][0]["content"].split("할 일: ", 1)[1])
        self.assertEqual({t["due_date"] for t in sent if t["id"] in self.ids}, {None})


if __name__ == "__main__":
    unittest.main()
