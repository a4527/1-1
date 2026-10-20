import os
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(os.environ.get("TASKFLOW_DB", Path(__file__).parents[2] / "tasks.db"))

COLUMNS = "id, title, description, due_date, priority, status, created_at"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT,
    due_date    TEXT,
    priority    TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('urgent', 'normal', 'low')),
    status      TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(SCHEMA)


def list_tasks() -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(f"SELECT {COLUMNS} FROM tasks ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_task(conn: sqlite3.Connection, task_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def create_task(title: str) -> dict:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        return get_task(conn, cur.lastrowid)  # type: ignore[arg-type]


def update_task(task_id: int, fields: dict) -> dict | None:
    with closing(_connect()) as conn, conn:
        if get_task(conn, task_id) is None:
            return None
        names = list(fields)  # 키는 pydantic 모델이 검증한 필드 이름뿐이다
        sets = ", ".join(f"{n} = ?" for n in names)
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", [*fields.values(), task_id])
        return get_task(conn, task_id)


def delete_task(task_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        return conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount > 0
