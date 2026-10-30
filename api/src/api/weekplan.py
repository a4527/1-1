import json
from datetime import date, timedelta

from . import store
from .suggest import _call_model, _fail, _load_json

MAX_TOKENS = 1024
MAX_TASKS = 30  # 너무 많이 보내면 답이 길어져 잘린다(잘리면 502)
DAY_COUNT = 7  # 이번 주 = 오늘부터 7일
EMPTY_NOTE = "이번 주는 비어 있어요"
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

WEEKPLAN_PROMPT = (
    "너는 이번 주 할 일 계획을 세워 주는 도우미야. "
    "입력으로 이번 주 날짜 목록(YYYY-MM-DD와 요일)과 아직 끝나지 않은 할 일 목록(JSON 배열)이 주어져. "
    "각 할 일은 id, title, priority(LOW/NORMAL/HIGH), due_date(YYYY-MM-DD 또는 null), overdue(기한 초과 여부)를 가져. "
    "모든 할 일을 이번 주 날짜 중 하루에 한 번씩 배치해. 마감일이 없는 할 일도 빠뜨리지 말고 여유 있는 날에 넣어. "
    "기한 초과는 첫날에, 마감일이 이번 주 안이면 그날이나 그 전에 두고, 하루에 일이 몰리지 않게 나눠. "
    "note에는 이번 주 계획을 한국어 한 문장으로 요약해. "
    "date는 입력에 있는 날짜만, id는 입력에 있는 것만 써. "
    '다른 말 없이 {"days": [{"date": ..., "ids": [...]}], "note": ...} 형태의 JSON 객체만 답해.'
)

WEEKPLAN_TEMPLATE = "이번 주 날짜: {days}\n할 일: {tasks}"


def _week(today: date) -> list[str]:
    return [(today + timedelta(days=i)).isoformat() for i in range(DAY_COUNT)]


def _fallback_day(task: dict, week: list[str]) -> str:
    """AI가 빠뜨린 할 일의 자리: 기한 초과는 첫날, 이번 주 마감은 그날, 나머지는 마지막 날."""
    if task["is_overdue"]:
        return week[0]
    if task["due_date"] in week:
        return task["due_date"]
    return week[-1]


def _rule_day(task: dict, day: str, week: list[str]) -> str:
    """AI가 고른 날이 규칙에 어긋나면 당긴다: 기한 초과는 첫날, 이번 주 마감은 마감일보다 늦지 않게."""
    if task["is_overdue"]:
        return week[0]
    if task["due_date"] in week and day > task["due_date"]:
        return task["due_date"]
    return day


def _parse(message, tasks: list[dict], week: list[str]) -> dict:
    data = _load_json(message)
    if not isinstance(data, dict):
        raise _fail()
    day_items, note = data.get("days"), data.get("note")
    if not isinstance(day_items, list) or not isinstance(note, str) or not note.strip():
        raise _fail()
    by_id = {t["id"]: t for t in tasks}
    plan: dict[str, list[int]] = {d: [] for d in week}
    placed: set[int] = set()
    for item in day_items:
        if not isinstance(item, dict) or not isinstance(item.get("ids", []), list):
            raise _fail()
        day = item.get("date")
        if day not in plan:  # 이번 주 밖이거나 형식이 틀린 날짜는 버린다
            continue
        for value in item.get("ids", []):
            if isinstance(value, int) and not isinstance(value, bool) and value in by_id and value not in placed:
                placed.add(value)
                plan[_rule_day(by_id[value], day, week)].append(value)
    for t in tasks:  # 마감 없는 일까지 모든 할 일이 표에 들어가게 한다
        if t["id"] not in placed:
            plan[_fallback_day(t, week)].append(t["id"])
    return {"days": [{"date": d, "ids": plan[d]} for d in week], "note": note.strip()}


def weekplan(owner_id: int) -> dict:
    """로그인한 사람의 끝나지 않은 할 일을 이번 주 7일에 나눈다. DB를 바꾸지 않는다."""
    today = date.today()
    week = _week(today)
    tasks = [t for t in store.list_tasks(owner_id) if t["status"] != "done"][:MAX_TASKS]
    if not tasks:
        return {"days": [{"date": d, "ids": []} for d in week], "note": EMPTY_NOTE}
    days = [f"{d}({WEEKDAYS[date.fromisoformat(d).weekday()]})" for d in week]
    items = [
        {"id": t["id"], "title": t["title"], "priority": t["priority"], "due_date": t["due_date"], "overdue": t["is_overdue"]}
        for t in tasks
    ]
    user_message = WEEKPLAN_TEMPLATE.format(days=", ".join(days), tasks=json.dumps(items, ensure_ascii=False))
    return _parse(_call_model(user_message, WEEKPLAN_PROMPT, MAX_TOKENS), tasks, week)
