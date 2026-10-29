import json
from datetime import date

from . import store
from .suggest import _call_model, _fail, _load_json

MAX_TOKENS = 1024
MAX_TASKS = 30  # 너무 많이 보내면 later가 길어져 답이 잘린다(잘리면 502)
TOP_COUNT = 3
EMPTY_CHEER = "오늘은 비어 있어요"

BRIEFING_PROMPT = (
    "너는 오늘 할 일을 정리해 주는 도우미야. "
    "입력으로 오늘 날짜(YYYY-MM-DD)와 아직 끝나지 않은 할 일 목록(JSON 배열)이 주어져. "
    "각 할 일은 id, title, priority(LOW/NORMAL/HIGH), due_date(YYYY-MM-DD 또는 null), overdue(기한 초과 여부)를 가져. "
    "기한 초과, 가까운 마감일, 높은 우선순위를 보고 오늘 먼저 할 일을 최대 3개 골라 top3에 넣고, "
    "각각 고른 이유를 reason에 한국어 한 문장으로 써. "
    "오늘 미뤄도 되는 할 일의 id는 later 배열에 넣어. "
    "cheer에는 오늘을 위한 짧은 응원 한 문장을 한국어로 써. "
    "id는 입력에 있는 것만 써. "
    '다른 말 없이 {"top3": [{"id": ..., "reason": ...}], "later": [...], "cheer": ...} 형태의 JSON 객체만 답해.'
)

BRIEFING_TEMPLATE = "오늘 날짜: {today}\n할 일: {tasks}"


def _known_id(value, known: set[int], seen: set[int]) -> bool:
    """보낸 적 있고 아직 안 쓴 정수 id만 받는다."""
    return isinstance(value, int) and not isinstance(value, bool) and value in known and value not in seen


def _parse(message, known: set[int]) -> dict:
    data = _load_json(message)
    if not isinstance(data, dict):
        raise _fail()
    top_items, later_items, cheer = data.get("top3"), data.get("later", []), data.get("cheer")
    if not isinstance(top_items, list) or not isinstance(later_items, list):
        raise _fail()
    if not isinstance(cheer, str) or not cheer.strip():
        raise _fail()
    seen: set[int] = set()
    top3 = []
    for item in top_items:
        if not isinstance(item, dict) or not isinstance(item.get("reason", ""), str):
            raise _fail()
        if len(top3) < TOP_COUNT and _known_id(item.get("id"), known, seen):
            seen.add(item["id"])
            top3.append({"id": item["id"], "reason": item.get("reason", "")})
    later = []
    for value in later_items:
        if _known_id(value, known, seen):
            seen.add(value)
            later.append(value)
    return {"top3": top3, "later": later, "cheer": cheer.strip()}


def briefing(owner_id: int) -> dict:
    """로그인한 사람의 끝나지 않은 할 일로 오늘 브리핑을 만든다. DB를 바꾸지 않는다."""
    tasks = [t for t in store.list_tasks(owner_id) if t["status"] != "done"][:MAX_TASKS]
    if not tasks:
        return {"top3": [], "later": [], "cheer": EMPTY_CHEER}
    items = [
        {"id": t["id"], "title": t["title"], "priority": t["priority"], "due_date": t["due_date"], "overdue": t["is_overdue"]}
        for t in tasks
    ]
    user_message = BRIEFING_TEMPLATE.format(
        today=date.today().isoformat(), tasks=json.dumps(items, ensure_ascii=False)
    )
    return _parse(_call_model(user_message, BRIEFING_PROMPT, MAX_TOKENS), {t["id"] for t in tasks})
