import json
import os
import re
from datetime import date
from typing import Literal

import anthropic
from fastapi import HTTPException

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 512
GENERATE_MAX_TOKENS = 2048
GENERATE_MAX_TASKS = 10

Priority = Literal["LOW", "NORMAL", "HIGH"]
PRIORITIES = ("LOW", "NORMAL", "HIGH")
DEFAULT_PRIORITY = "NORMAL"

SYSTEM_PROMPT = (
    "너는 할 일(Task)의 우선순위와 마감일을 제안하는 도우미야. "
    "입력으로 Task의 Title, Description, 오늘 날짜(YYYY-MM-DD)가 주어져. "
    "오늘 날짜를 기준으로 '내일', '이번 주' 같은 표현을 계산해. "
    "priority는 LOW, NORMAL, HIGH 중 하나이고 확실하지 않으면 NORMAL로 해. "
    "due_date는 YYYY-MM-DD 형식이거나, 마감일을 알 수 없으면 null이야. "
    "reason에는 그렇게 제안한 이유를 한 문장으로 써. "
    '다른 말 없이 {"priority": ..., "due_date": ..., "reason": ...} 형태의 JSON 객체만 답해.'
)

USER_TEMPLATE = "Title: {title}\nDescription: {description}\n오늘 날짜: {today}"

GENERATE_PROMPT = (
    "너는 주제를 받아 그와 관련된 할 일(Task) 목록을 만들어 주는 도우미야. "
    "입력으로 주제, 설명, 오늘 날짜(YYYY-MM-DD)가 주어져. "
    "주제와 설명을 바탕으로 서로 겹치지 않는 구체적인 할 일을 5개 만들어. "
    "주제와 설명이 부족해서 할 일을 만들기 애매하면 지어내지 말고 tasks를 빈 배열로 두고, "
    "reason에 무엇이 부족한지 한 문장으로 써. 할 일을 만들었다면 reason에는 만든 기준을 한 문장으로 써. "
    "각 할 일은 title(100자 이내), description(짧은 설명), priority, due_date를 가져. "
    "priority는 LOW, NORMAL, HIGH 중 하나이고 확실하지 않으면 NORMAL로 해. "
    "due_date는 오늘 날짜 기준의 YYYY-MM-DD 형식이거나, 마감일이 필요 없으면 null이야. "
    '다른 말 없이 {"reason": ..., "tasks": [{"title": ..., "description": ..., "priority": ..., "due_date": ...}]} 형태의 JSON 객체만 답해.'
)

GENERATE_TEMPLATE = "주제: {topic}\n설명: {description}\n오늘 날짜: {today}"

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$", re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fail() -> HTTPException:
    return HTTPException(status_code=502, detail="제안 실패")


def _call_model(user_message: str, system: str = SYSTEM_PROMPT, max_tokens: int = MAX_TOKENS) -> anthropic.types.Message:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="AI 기능 꺼짐")
    client = anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1)
    try:
        return client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise HTTPException(status_code=503, detail="AI 기능 꺼짐") from None
    except anthropic.RateLimitError:
        raise HTTPException(status_code=503, detail="AI 사용 한도에 도달했습니다. 잠시 후 다시 시도하세요.") from None
    except (anthropic.InternalServerError, anthropic.APIConnectionError):
        raise HTTPException(status_code=503, detail="AI가 바쁩니다. 잠시 후 다시 시도하세요.") from None
    except anthropic.APIError:
        raise _fail() from None


def _load_json(message: anthropic.types.Message):
    if message.stop_reason != "end_turn":  # max_tokens(잘림), refusal 등
        raise _fail()
    text = "".join(b.text for b in message.content if b.type == "text")
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except ValueError:
        raise _fail() from None


def _check_priority(value) -> str:
    if value not in PRIORITIES:
        raise _fail()
    return value


def _check_due_date(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise _fail()
    try:
        date.fromisoformat(value)
    except ValueError:
        raise _fail() from None
    return value


def _parse(message: anthropic.types.Message) -> dict:
    data = _load_json(message)
    if not isinstance(data, dict):
        raise _fail()
    priority = _check_priority(data.get("priority", DEFAULT_PRIORITY))
    due = _check_due_date(data.get("due_date"))
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise _fail()
    return {"priority": priority, "due_date": due, "reason": reason}


def _parse_tasks(message: anthropic.types.Message) -> dict:
    data = _load_json(message)
    items = data.get("tasks") if isinstance(data, dict) else data
    reason = data.get("reason", "") if isinstance(data, dict) else ""
    if not isinstance(items, list) or not isinstance(reason, str):
        raise _fail()
    if not items and not reason.strip():  # 못 만들었다면 이유라도 있어야 한다
        raise _fail()
    tasks = []
    for item in items[:GENERATE_MAX_TASKS]:
        if not isinstance(item, dict):
            raise _fail()
        title = item.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
            raise _fail()
        description = item.get("description", "")
        if not isinstance(description, str) or len(description) > 1000:
            raise _fail()
        tasks.append(
            {
                "title": title.strip(),
                "description": description,
                "priority": _check_priority(item.get("priority", DEFAULT_PRIORITY)),
                "due_date": _check_due_date(item.get("due_date")),
            }
        )
    return {"tasks": tasks, "reason": reason}


def suggest(title: str, description: str) -> dict:
    """DB를 건드리지 않고 제안만 돌려준다."""
    user_message = USER_TEMPLATE.format(title=title, description=description, today=date.today().isoformat())
    return _parse(_call_model(user_message))


def generate(topic: str, description: str) -> dict:
    """주제·설명에 맞는 Task 후보를 만든다. 정보가 부족하면 tasks 없이 이유만 준다. DB를 건드리지 않는다."""
    user_message = GENERATE_TEMPLATE.format(topic=topic, description=description, today=date.today().isoformat())
    return _parse_tasks(_call_model(user_message, GENERATE_PROMPT, GENERATE_MAX_TOKENS))
