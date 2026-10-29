"""POST /api/tasks/briefing 시나리오. Anthropic 호출은 모킹하고, 실제 API는 부르지 않는다.

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
URL = "/api/tasks/briefing"


def reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def answer(top3=(), later=(), cheer="힘내요") -> SimpleNamespace:
    return reply(json.dumps({"top3": list(top3), "later": list(later), "cheer": cheer}, ensure_ascii=False))


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


class Briefing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmp.name) / "briefing.db"
        env = {**os.environ, "TASKFLOW_DB": str(store.DB_PATH)}
        subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True, env=env)
        cls.client = signup("briefing@example.com")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cls.late = add(cls.client, "보고서", description="비밀 설명", due_date=yesterday, priority="HIGH")
        cls.mid = add(cls.client, "장보기", status="in_progress")
        cls.low = add(cls.client, "책 읽기", priority="LOW")
        cls.extra = add(cls.client, "운동")
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

    def test_ok_and_what_is_sent(self) -> None:
        msg = answer([{"id": self.late, "reason": "기한이 지났어요"}], [self.low], "오늘도 화이팅")
        res, create = self.call(msg)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(), {"top3": [{"id": self.late, "reason": "기한이 지났어요"}], "later": [self.low], "cheer": "오늘도 화이팅"}
        )
        kw = create.call_args.kwargs
        self.assertEqual((kw["model"], kw["thinking"]), ("claude-haiku-5-5", {"type": "disabled"}))
        content = kw["messages"][0]["content"]
        self.assertIn(f"오늘 날짜: {date.today().isoformat()}", content)
        sent = json.loads(content.split("할 일: ", 1)[1])
        self.assertEqual({t["id"] for t in sent}, {self.late, self.mid, self.low, self.extra})  # done·남의 일 제외
        self.assertEqual(set(sent[0]), {"id", "title", "priority", "due_date", "overdue"})  # 설명 없음
        self.assertNotIn("비밀 설명", content)
        late = next(t for t in sent if t["id"] == self.late)
        self.assertEqual((late["title"], late["priority"], late["overdue"]), ("보고서", "HIGH", True))

    def test_empty_does_not_call_model(self) -> None:
        res, create = self.call(answer(), client=self.empty)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"top3": [], "later": [], "cheer": "오늘은 비어 있어요"})
        create.assert_not_called()

    def test_unknown_ids_dropped_and_top3_capped(self) -> None:
        top3 = [
            {"id": 9999, "reason": "없는 일"},
            {"id": self.other_id, "reason": "남의 일"},
            {"id": self.done, "reason": "끝난 일"},
            {"id": str(self.mid), "reason": "문자열 id"},
            {"id": self.late, "reason": "a"},
            {"id": self.late, "reason": "중복"},
            {"id": self.mid, "reason": "b"},
            {"id": self.low, "reason": "c"},
            {"id": self.extra, "reason": "넷째"},
        ]
        later = [self.extra, self.late, 9999, self.other_id, True, self.extra]
        res, _ = self.call(answer(top3, later))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([t["id"] for t in res.json()["top3"]], [self.late, self.mid, self.low])
        self.assertEqual(res.json()["later"], [self.extra])

    def test_bad_output_is_502(self) -> None:
        bad = [
            reply("JSON 아님"),
            reply("[1, 2]"),
            reply('{"later": [], "cheer": "c"}'),
            reply('{"top3": {}, "later": [], "cheer": "c"}'),
            reply('{"top3": [], "later": 3, "cheer": "c"}'),
            reply('{"top3": [1], "later": [], "cheer": "c"}'),
            reply('{"top3": [{"id": 1, "reason": 3}], "later": [], "cheer": "c"}'),
            reply('{"top3": [], "later": []}'),
            reply('{"top3": [], "later": [], "cheer": "  "}'),
            reply('{"top3": [{"id": 1', stop_reason="max_tokens"),
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

    def test_needs_login(self) -> None:
        anon = TestClient(app, base_url="http://localhost")
        self.assertEqual(anon.post(URL).status_code, 401)


if __name__ == "__main__":
    unittest.main()
