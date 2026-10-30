"""한 문장 명령의 입력과 제안 검증 규칙 (#19). 저장은 하지 않는다."""
import re
from datetime import date
from typing import Annotated

from pydantic import StringConstraints


CommandText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def valid_due(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def mentions_due(text: str, due) -> bool:
    """문장에 그 마감일이 10-30 · 10/30 · 30일 모양으로 들어 있는지 본다."""
    if due is None or not valid_due(due):
        return False
    d = date.fromisoformat(due)
    pattern = rf"(?<!\d)0?{d.month}\s*[-/]\s*0?{d.day}(?!\d)|(?<!\d)0?{d.day}\s*일"
    return re.search(pattern, text) is not None


def clean_action(item, known: set[int]) -> dict | None:
    if not isinstance(item, dict):
        return None
    # 우선순위 변경 명령은 지원하지 않는다. 잘못된 우선순위가 붙은 동작도 버린다.
    if "priority" in item and item["priority"] not in ("LOW", "NORMAL", "HIGH"):
        return None
    kind = item.get("kind")
    if kind == "add":
        title = item.get("title")
        if (item.get("id") is not None or item.get("value") is not None
                or not isinstance(title, str) or not 1 <= len(title.strip()) <= 100):
            return None
        return {"kind": "add", "id": None, "title": title.strip(), "value": None}
    task_id = item.get("id")
    if type(task_id) is not int or task_id not in known:
        return None
    if kind == "due" and "value" in item and valid_due(item["value"]):
        return {"kind": "due", "id": task_id, "title": None, "value": item["value"]}
    if kind == "done" and item.get("value") is None:
        return {"kind": "done", "id": task_id, "title": None, "value": None}
    return None
