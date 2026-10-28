"""POST /api/tasks/suggest 시나리오. Anthropic 호출은 모킹하고, 실제 API는 부르지 않는다.

    uv run python -m unittest discover -s tests
"""
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx
from fastapi.testclient import TestClient

from api import store
from api.main import app

API_DIR = Path(__file__).parents[1]
URL = "/api/tasks/suggest"
BODY = {"title": "보고서 제출", "description": "내일까지 팀장에게"}


def reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def status_error(cls, code: int):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(code, request=req), body=None)


class Suggest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmp.name) / "suggest.db"
        env = {**os.environ, "TASKFLOW_DB": str(store.DB_PATH)}
        subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True, env=env)
        cls.client = TestClient(app, base_url="http://localhost")
        cred = {"email": "suggest@example.com", "password": "password-1"}
        assert cls.client.post("/api/auth/signup", json=cred).status_code == 201
        cls.client.post("/api/tasks", json={"title": "기존"})

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

    def call(self, message=None, error=None, body=BODY):
        create = mock.Mock(return_value=message, side_effect=error)
        fake = mock.Mock()
        fake.messages.create = create
        with mock.patch("api.suggest.anthropic.Anthropic", return_value=fake):
            res = self.client.post(URL, json=body)
        self.assertEqual(self.dump(), self.before)  # 어떤 경우에도 DB는 그대로
        return res, create

    def test_ok(self) -> None:
        text = '{"priority": "HIGH", "due_date": "2026-10-29", "reason": "내일 마감"}'
        res, create = self.call(reply(text))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"priority": "HIGH", "due_date": "2026-10-29", "reason": "내일 마감"})
        kw = create.call_args.kwargs
        self.assertEqual(kw["model"], "claude-haiku-5-5")
        self.assertEqual(kw["thinking"], {"type": "disabled"})
        self.assertIn(date.today().isoformat(), kw["messages"][0]["content"])
        self.assertIn("보고서 제출", kw["messages"][0]["content"])

    def test_fenced_and_defaults(self) -> None:
        res, _ = self.call(reply('```json\n{"due_date": null, "reason": "r"}\n```'))
        self.assertEqual(res.json(), {"priority": "NORMAL", "due_date": None, "reason": "r"})

    def test_bad_output_is_502(self) -> None:
        bad = [
            reply('{"priority": "URGENT", "due_date": null, "reason": "r"}'),
            reply('{"priority": "low", "due_date": null, "reason": "r"}'),
            reply('{"priority": "LOW", "due_date": "내일", "reason": "r"}'),
            reply('{"priority": "LOW", "due_date": "2026-13-40", "reason": "r"}'),
            reply('{"priority": "LOW", "due_date": "2026-1-5", "reason": "r"}'),
            reply('{"priority": "LOW", "due_date": 20261029, "reason": "r"}'),
            reply('{"priority": "LOW", "due_date": null, "reason": 3}'),
            reply("JSON 아님"),
            reply("[1, 2]"),
            reply('{"priority": "HIGH", "due_da', stop_reason="max_tokens"),
            reply("", stop_reason="refusal"),
        ]
        for message in bad:
            with self.subTest(text=message.content[0].text, stop=message.stop_reason):
                res, _ = self.call(message)
                self.assertEqual(res.status_code, 502)
                self.assertEqual(res.json()["detail"], "제안 실패")

    def test_no_key_is_503(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop("ANTHROPIC_API_KEY")
            res, create = self.call(reply("{}"))
        self.assertEqual((res.status_code, res.json()["detail"]), (503, "AI 기능 꺼짐"))
        create.assert_not_called()

    def test_limit_and_busy_are_503(self) -> None:
        for err in (
            status_error(anthropic.RateLimitError, 429),
            status_error(anthropic.InternalServerError, 529),
            anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
        ):
            with self.subTest(err=type(err).__name__):
                res, _ = self.call(error=err)
                self.assertEqual(res.status_code, 503)
                self.assertTrue(res.json()["detail"])

    def test_bad_key_is_503_and_other_errors_502(self) -> None:
        res, _ = self.call(error=status_error(anthropic.AuthenticationError, 401))
        self.assertEqual((res.status_code, res.json()["detail"]), (503, "AI 기능 꺼짐"))
        res, _ = self.call(error=status_error(anthropic.BadRequestError, 400))
        self.assertEqual((res.status_code, res.json()["detail"]), (502, "제안 실패"))

    def test_request_validation_and_auth(self) -> None:
        res, create = self.call(reply("{}"), body={"title": "   "})
        self.assertEqual(res.status_code, 422)
        create.assert_not_called()
        res, _ = self.call(reply("{}"), body={"title": "x", "priority": "HIGH"})
        self.assertEqual(res.status_code, 422)
        anon = TestClient(app, base_url="http://localhost")
        self.assertEqual(anon.post(URL, json=BODY).status_code, 401)


if __name__ == "__main__":
    unittest.main()
