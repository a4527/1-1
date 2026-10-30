"""미션 #19. 실제 AI 호출 없이 API 계약과 DB 불변을 검증한다."""
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import anthropic
from fastapi.testclient import TestClient

from api import store
from api.main import app
from test_briefing import add, reply, signup, status_error

URL = "/api/tasks/command"


def answer(actions=(), ask=None):
    return reply(json.dumps({"actions": list(actions), "ask": ask}, ensure_ascii=False))


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_path = store.DB_PATH
        store.DB_PATH = Path(cls.tmp.name) / "command.db"
        subprocess.run(
            ["alembic", "upgrade", "head"], cwd=Path(__file__).parents[1], check=True,
            capture_output=True, env={**os.environ, "TASKFLOW_DB": str(store.DB_PATH)},
        )
        cls.client = signup("command@example.com")
        cls.mine = add(cls.client, "보고서", description="비밀 설명", priority="HIGH", due_date="2026-01-01")
        cls.active = add(cls.client, "진행 중", status="in_progress")
        cls.done = add(cls.client, "끝난 일", status="done")
        cls.other = signup("command-other@example.com")
        cls.theirs = add(cls.other, "남의 일")
        cls.empty = signup("command-empty@example.com")

    @classmethod
    def tearDownClass(cls):
        store.DB_PATH = cls.old_path
        cls.tmp.cleanup()

    def dump(self):
        with sqlite3.connect(store.DB_PATH) as conn:
            return list(conn.iterdump())

    def call(self, message=None, *, body=None, error=None, client=None):
        before = self.dump()
        fake = mock.Mock()
        fake.messages.create = mock.Mock(return_value=message, side_effect=error)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), mock.patch(
            "api.suggest.anthropic.Anthropic", return_value=fake,
        ):
            res = (client or self.client).post(URL, json=body if body is not None else {"text": "보고서 내일로"})
        self.assertEqual(self.dump(), before)
        return res, fake.messages.create

    def test_actions_and_payload(self):
        actions = [
            {"kind": "add", "id": None, "title": " 장보기 ", "value": None},
            {"kind": "due", "id": self.mine, "title": None, "value": "2026-10-31"},
            {"kind": "done", "id": self.active, "title": None, "value": None},
        ]
        res, create = self.call(answer(actions, "질문은 무시"))
        self.assertEqual(res.status_code, 200)
        actions[0]["title"] = "장보기"
        self.assertEqual(res.json(), {"actions": actions, "ask": None})
        payload = json.loads(create.call_args.kwargs["messages"][0]["content"])
        self.assertEqual(payload["today"], date.today().isoformat())
        self.assertEqual(payload["text"], "보고서 내일로")
        self.assertEqual({t["id"] for t in payload["tasks"]}, {self.mine, self.active})
        self.assertEqual(set(payload["tasks"][0]), {"id", "title", "priority", "due_date", "overdue"})
        self.assertNotIn("비밀 설명", json.dumps(payload, ensure_ascii=False))

    def test_input_validation_and_boundaries(self):
        for body in ({}, {"text": ""}, {"text": " \n "}, {"text": "가" * 201},
                     {"text": None}, {"text": 5}, {"text": "a", "extra": True}):
            with self.subTest(body=body):
                res, create = self.call(body=body)
                self.assertEqual(res.status_code, 422)
                self.assertTrue(res.json()["detail"])
                create.assert_not_called()
        for text in ("가", "가" * 200, "  장보기  "):
            res, create = self.call(answer(), body={"text": text})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(json.loads(create.call_args.kwargs["messages"][0]["content"])["text"], text.strip())

    def test_unknown_ids_dates_priorities_and_unsupported_actions_dropped(self):
        bad = [
            {"kind": "done", "id": task_id} for task_id in
            (999999, self.theirs, self.done, str(self.mine), True, float(self.mine), None)
        ]
        bad += [{"kind": "due", "id": self.mine, "value": value} for value in
                ("2026-02-30", "2026-1-01", "2026-10-30T00:00:00", "내일", 123, [], {})]
        bad += [
            {"kind": "delete", "id": self.mine}, {"kind": "priority", "id": self.mine, "value": "HIGH"},
            {"kind": "due", "id": self.mine},
            {"kind": "done", "id": self.mine, "value": "done"},
            {"kind": "add", "title": "x", "priority": "URGENT"},
            {"kind": "add", "title": "x", "value": "HIGH"},
            {"kind": "add", "title": "x", "id": self.theirs},
            {"kind": "add", "title": " "}, {"kind": "add", "title": "가" * 101},
            None, 3, [],
        ]
        res, _ = self.call(answer(bad))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["actions"], [])
        self.assertTrue(res.json()["ask"])
        valid = {"kind": "due", "id": self.mine, "value": None}
        res, _ = self.call(answer(bad + [valid, valid]))
        self.assertEqual(res.json(), {"actions": [{**valid, "title": None}], "ask": None})
        for due in ("2020-01-01", "2028-02-29"):
            res, _ = self.call(answer([{"kind": "due", "id": self.mine, "value": due}]))
            self.assertEqual(res.json()["actions"][0]["value"], due)

    def test_empty_tasks_still_allows_add(self):
        res, create = self.call(answer([{"kind": "add", "title": "새 일"}]), client=self.empty)
        self.assertEqual(res.json()["actions"][0]["title"], "새 일")
        self.assertEqual(json.loads(create.call_args.kwargs["messages"][0]["content"])["tasks"], [])

    def test_only_sent_ids_are_allowed(self):
        tasks = [{"id": 1000 + n, "title": "일", "status": "todo", "priority": "NORMAL",
                  "due_date": None, "is_overdue": False} for n in range(31)]
        with mock.patch("api.command.store.list_tasks", return_value=tasks):
            res, create = self.call(answer([{"kind": "done", "id": 1030}]))
        self.assertEqual(len(json.loads(create.call_args.kwargs["messages"][0]["content"])["tasks"]), 30)
        self.assertEqual(res.json()["actions"], [])

    def test_ask(self):
        res, _ = self.call(answer(ask="어느 할 일인가요?"))
        self.assertEqual(res.json(), {"actions": [], "ask": "어느 할 일인가요?"})
        for ask in (None, " ", "어느 일인가요? 언제인가요?", "질문\n둘"):
            res, _ = self.call(answer(ask=ask))
            self.assertTrue(res.json()["ask"])
            self.assertNotIn("\n", res.json()["ask"])

    def test_malformed_output_502(self):
        for message in (reply("no JSON"), reply("[]"), reply("{}"), reply('{"actions":{}}'),
                        answer(ask=3), reply("{}", "max_tokens"), reply("", "refusal")):
            res, _ = self.call(message)
            self.assertEqual((res.status_code, res.json()["detail"]), (502, "제안 실패"))

    def test_ai_errors(self):
        cases = [(anthropic.AuthenticationError, 401, 503), (anthropic.PermissionDeniedError, 403, 503),
                 (anthropic.RateLimitError, 429, 503), (anthropic.InternalServerError, 500, 503),
                 (anthropic.BadRequestError, 400, 502)]
        for cls, code, expected in cases:
            res, _ = self.call(error=status_error(cls, code))
            self.assertEqual(res.status_code, expected)
        import httpx
        res, _ = self.call(error=anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.com")))
        self.assertEqual(res.status_code, 503)

    def test_missing_key_and_login(self):
        before = self.dump()
        with mock.patch.dict(os.environ):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            res = self.client.post(URL, json={"text": "장보기 추가"})
        self.assertEqual((res.status_code, res.json()["detail"]), (503, "AI 기능 꺼짐"))
        anon = TestClient(app, base_url="http://localhost")
        self.assertEqual(anon.post(URL, json={"text": "장보기 추가"}).status_code, 401)
        self.assertEqual(self.dump(), before)

    def test_openapi_contract(self):
        spec = self.client.get("/openapi.json").json()
        route = spec["paths"][URL]["post"]
        self.assertEqual(route["responses"]["200"]["content"]["application/json"]["schema"],
                         {"$ref": "#/components/schemas/CommandResponse"})
        text_schema = spec["components"]["schemas"]["CommandRequest"]["properties"]["text"]
        self.assertEqual((text_schema["minLength"], text_schema["maxLength"]), (1, 200))


class Ambiguous(unittest.TestCase):
    """같은 제목 카드가 둘 이상이면 마감일 없는 문장은 되묻는다."""
    call = Command.call
    dump = Command.dump

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_path = store.DB_PATH
        store.DB_PATH = Path(cls.tmp.name) / "ambiguous.db"
        subprocess.run(
            ["alembic", "upgrade", "head"], cwd=Path(__file__).parents[1], check=True,
            capture_output=True, env={**os.environ, "TASKFLOW_DB": str(store.DB_PATH)},
        )
        cls.client = signup("ambiguous@example.com")
        cls.first = add(cls.client, "보고서", due_date="2026-10-30")
        cls.second = add(cls.client, "보고서", due_date="2026-11-02")
        cls.no_due = [add(cls.client, "회의"), add(cls.client, "회의")]
        cls.single = add(cls.client, "장보기", due_date="2026-10-30")

    @classmethod
    def tearDownClass(cls):
        store.DB_PATH = cls.old_path
        cls.tmp.cleanup()

    def due(self, task_id):
        return {"kind": "due", "id": task_id, "title": None, "value": "2026-11-02"}

    def test_same_title_without_due_asks(self):
        res, _ = self.call(answer([self.due(self.first)]), body={"text": "보고서 마감 월요일로"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {
            "actions": [],
            "ask": "「보고서」가 2개 있어요 — 어느 것인지 마감일을 붙여 말해 주세요(예: 10-30 보고서)",
        })

    def test_same_title_with_due_passes(self):
        for text in ("10-30 보고서 마감 월요일로", "10/30 보고서 마감 월요일로", "30일 보고서 마감 월요일로"):
            with self.subTest(text=text):
                res, _ = self.call(answer([self.due(self.first)]), body={"text": text})
                self.assertEqual(res.json(), {"actions": [self.due(self.first)], "ask": None})
        res, _ = self.call(answer([self.due(self.second)]), body={"text": "11/2 보고서 월요일로"})
        self.assertEqual(res.json()["actions"], [self.due(self.second)])

    def test_other_card_due_still_asks(self):
        res, _ = self.call(answer([self.due(self.second)]), body={"text": "10-30 보고서 월요일로"})
        self.assertEqual(res.json()["actions"], [])
        self.assertIn("2개", res.json()["ask"])

    def test_same_title_without_any_due_asks(self):
        res, _ = self.call(answer([{"kind": "done", "id": self.no_due[0]}]), body={"text": "회의 끝"})
        self.assertEqual(res.json()["actions"], [])
        self.assertIn("「회의」가 2개", res.json()["ask"])

    def test_single_title_and_add_unaffected(self):
        res, _ = self.call(answer([self.due(self.single), {"kind": "add", "title": "보고서"}]),
                           body={"text": "장보기 월요일로, 보고서 추가"})
        self.assertEqual(len(res.json()["actions"]), 2)


if __name__ == "__main__":
    unittest.main()
