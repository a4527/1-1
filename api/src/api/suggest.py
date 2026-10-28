import json
import os
import re
from datetime import date
from typing import Literal

import anthropic
from fastapi import HTTPException

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 512

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

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$", re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fail() -> HTTPException:
    return HTTPException(status_code=502, detail="제안 실패")


def _call_model(user_message: str) -> anthropic.types.Message:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="AI 기능 꺼짐")
    client = anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1)
    try:
        return client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "disabled"},
            system=SYSTEM_PROMPT,
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


def _parse(message: anthropic.types.Message) -> dict:
    if message.stop_reason != "end_turn":  # max_tokens(잘림), refusal 등
        raise _fail()
    text = "".join(b.text for b in message.content if b.type == "text")
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except ValueError:
        raise _fail() from None
    if not isinstance(data, dict):
        raise _fail()

    priority = data.get("priority", DEFAULT_PRIORITY)
    if priority not in PRIORITIES:
        raise _fail()

    due = data.get("due_date")
    if due is not None:
        if not isinstance(due, str) or not _DATE_RE.match(due):
            raise _fail()
        try:
            date.fromisoformat(due)
        except ValueError:
            raise _fail() from None

    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise _fail()
    return {"priority": priority, "due_date": due, "reason": reason}


def suggest(title: str, description: str) -> dict:
    """DB를 건드리지 않고 제안만 돌려준다."""
    user_message = USER_TEMPLATE.format(title=title, description=description, today=date.today().isoformat())
    return _parse(_call_model(user_message))
