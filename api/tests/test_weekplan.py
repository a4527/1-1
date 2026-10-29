"""POST /api/tasks/weekplan 시나리오. Anthropic 호출은 모킹하고, 실제 API는 부르지 않는다.

    uv run python -m unittest discover -s tests
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx
from fastapi.testclient import TestClient

from api import store
from api.main import app

API_DIR = Path(__file__).parents[1]
URL = "/api/tasks/weekplan"
TODAY = date.today()
WEEK = [(TODAY + timedelta(days=i)).isoformat() for i in range(7)]


def reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def answer(days=(), note="고르게 나눴어요") -> SimpleNamespace:
    return reply(json.dumps({"days": list(days), "note": note}, ensure_ascii=False))


def status_error(cls, code: int):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(code, request=req), body=None)


def signup(email: str) -> TestClient:
    client = TestClient(app, base_url="http://localhost")
    assert client.post("/api/auth/signup", json={"email": email, "password": "password-1"}).status_code == 201
    return client


def add(client: TestClient, title: str, **fields) -> int:
    task_id = client.post("/api/tasks", json={"title": title}).json()["id"]
    if fields:
        assert client.patch(f"/api/tasks/{task_id}", json=fields).status_code == 200
    return task_id


class WeekPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmp.name) / "weekplan.db"
        env = {**os.environ, "TASKFLOW_DB": str(store.DB_PATH)}
        subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True, env=env)
        cls.client = signup("weekplan@example.com")
        yesterday = (TODAY - timedelta(days=1)).isoformat()
        cls.late = add(cls.client, "보고서", description="비밀 설명", due_date=yesterday, priority="HIGH")
        cls.soon = add(cls.client, "발표 준비", due_date=WEEK[2])
        cls.free = add(cls.client, "책 읽기")  # 마감 없음
        cls.far = add(cls.client, "여행 계획", due_date=(TODAY + timedelta(days=30)).isoformat())
        cls.done = add(cls.client, "끝난 일", status="done")
        cls.other = signup("other@example.com")
        cls.other_id = add(cls.other, "남의 일")
        cls.empty = signup("empty@example.com")
        add(cls.empty, "다 했다", status="done")

    @classmethod
    def tearDownClass(cls) -> None:
        store.DB_PATH = cls._old_path
        cls._tmp.cleanup()

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.before = self.dump()

    def dump(self) -> list:
        with sqlite3.connect(store.DB_PATH) as conn:
            return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()

    def call(self, message=None, error=None, client=None):
        create = mock.Mock(return_value=message, side_effect=error)
        fake = mock.Mock()
        fake.messages.create = create
        with mock.patch("api.suggest.anthropic.Anthropic", return_value=fake):
            res = (client or self.client).post(URL)
        self.assertEqual(self.dump(), self.before)  # 어떤 경우에도 DB는 그대로
        return res, create

    def plan(self, res) -> dict:
        return {d["date"]: d["ids"] for d in res.json()["days"]}

    def test_ok_and_what_is_sent(self) -> None:
        days = [
            {"date": WEEK[0], "ids": [self.late]},
            {"date": WEEK[1], "ids": [self.soon, self.free]},
            {"date": WEEK[4], "ids": [self.far]},
        ]
        res, create = self.call(answer(days, "이번 주는 보고서부터"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["note"], "이번 주는 보고서부터")
        self.assertEqual([d["date"] for d in res.json()["days"]], WEEK)  # 오늘부터 7일, 빈 날도 있다
        plan = self.plan(res)
        self.assertEqual((plan[WEEK[0]], plan[WEEK[1]], plan[WEEK[4]], plan[WEEK[6]]), ([self.late], [self.soon, self.free], [self.far], []))
        kw = create.call_args.kwargs
        self.assertEqual((kw["model"], kw["thinking"]), ("claude-haiku-5-5", {"type": "disabled"}))
        content = kw["messages"][0]["content"]
        self.assertIn(WEEK[0], content)
        self.assertIn(WEEK[6], content)
        sent = json.loads(content.split("할 일: ", 1)[1])
        self.assertEqual({t["id"] for t in sent}, {self.late, self.soon, self.free, self.far})  # done·남의 일 제외
        self.assertEqual(set(sent[0]), {"id", "title", "priority", "due_date", "overdue"})  # 설명 없음
        self.assertNotIn("비밀 설명", content)

    def test_missing_tasks_still_in_table(self) -> None:
        res, _ = self.call(answer([]))
        self.assertEqual(res.status_code, 200)
        plan = self.plan(res)
        self.assertEqual(plan[WEEK[0]], [self.late])  # 기한 초과는 첫날
        self.assertEqual(plan[WEEK[2]], [self.soon])  # 이번 주 마감은 그날
        self.assertEqual(plan[WEEK[6]], [self.far, self.free])  # 먼 마감·마감 없음은 마지막 날(보드 순서)

    def test_unknown_ids_and_dates_dropped(self) -> None:
        days = [
            {"date": WEEK[0], "ids": [9999, self.other_id, self.done, str(self.free), True, self.late, self.late]},
            {"date": WEEK[1], "ids": [self.late, self.soon]},
            {"date": "다음주", "ids": [self.free]},
            {"date": (TODAY + timedelta(days=8)).isoformat(), "ids": [self.far]},
        ]
        res, _ = self.call(answer(days))
        plan = self.plan(res)
        self.assertEqual(plan[WEEK[0]], [self.late])
        self.assertEqual(plan[WEEK[1]], [self.soon])
        self.assertEqual(plan[WEEK[6]], [self.far, self.free])
        self.assertEqual(sorted(i for ids in plan.values() for i in ids), sorted([self.late, self.soon, self.free, self.far]))

    def test_empty_does_not_call_model(self) -> None:
        res, create = self.call(answer(), client=self.empty)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"days": [{"date": d, "ids": []} for d in WEEK], "note": "이번 주는 비어 있어요"})
        create.assert_not_called()

    def test_bad_output_is_502(self) -> None:
        bad = [
            reply("JSON 아님"),
            reply("[1, 2]"),
            reply('{"note": "n"}'),
            reply('{"days": {}, "note": "n"}'),
            reply('{"days": [1], "note": "n"}'),
            reply('{"days": [{"date": "2026-01-01", "ids": 3}], "note": "n"}'),
            reply('{"days": []}'),
            reply('{"days": [], "note": "  "}'),
            reply('{"days": [{"date": "2026', stop_reason="max_tokens"),
            reply("", stop_reason="refusal"),
        ]
        for message in bad:
            with self.subTest(text=message.content[0].text, stop=message.stop_reason):
                res, _ = self.call(message)
                self.assertEqual((res.status_code, res.json()["detail"]), (502, "제안 실패"))

    def test_no_key_and_limit_are_503(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop("ANTHROPIC_API_KEY")
            res, create = self.call(answer())
        self.assertEqual((res.status_code, res.json()["detail"]), (503, "AI 기능 꺼짐"))
        create.assert_not_called()
        res, _ = self.call(error=status_error(anthropic.RateLimitError, 429))
        self.assertEqual(res.status_code, 503)


if __name__ == "__main__":
    unittest.main()
