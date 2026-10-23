import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("TASKFLOW_DB", Path(__file__).parents[2] / "tasks.db"))

COLUMNS = "id, title, description, due_date, priority, status, created_at"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_schema() -> None:
    """표는 alembic이 만든다. 이전이 안 된 DB로는 서버를 켜지 않는다."""
    with closing(_connect()) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        task_cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
    if not {"users", "sessions", "tasks"} <= names or "owner_id" not in task_cols:
        raise RuntimeError(f"DB({DB_PATH})가 최신이 아닙니다. 백업 후 `cd api && uv run alembic upgrade head`를 실행하세요.")


def list_tasks(owner_id: int) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE owner_id = ? ORDER BY id", (owner_id,)).fetchall()
    return [dict(r) for r in rows]


def get_task(conn: sqlite3.Connection, owner_id: int, task_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).fetchone()
    return dict(row) if row else None


def create_task(owner_id: int, title: str) -> dict:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("INSERT INTO tasks (owner_id, title) VALUES (?, ?)", (owner_id, title))
        return get_task(conn, owner_id, cur.lastrowid)  # type: ignore[arg-type]


def update_task(owner_id: int, task_id: int, fields: dict) -> dict | None:
    with closing(_connect()) as conn, conn:
        if get_task(conn, owner_id, task_id) is None:
            return None
        names = list(fields)  # 키는 pydantic 모델이 검증한 필드 이름뿐이다
        sets = ", ".join(f"{n} = ?" for n in names)
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ? AND owner_id = ?", [*fields.values(), task_id, owner_id])
        return get_task(conn, owner_id, task_id)


def delete_task(owner_id: int, task_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        return conn.execute("DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).rowcount > 0


# --- 사용자 · 세션 ---


def get_user_by_email(email: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def create_user(email: str, password_hash: str) -> dict | None:
    """이메일이 이미 있으면 None."""
    try:
        with closing(_connect()) as conn, conn:
            cur = conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash))
            return {"id": cur.lastrowid, "email": email}
    except sqlite3.IntegrityError:
        return None


def claim_user(user_id: int, password_hash: str) -> bool:
    """비밀번호 없는 계정(M2 이전 Task 주인)에만 비밀번호를 붙인다."""
    with closing(_connect()) as conn, conn:
        return (
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ? AND password_hash IS NULL", (password_hash, user_id)
            ).rowcount
            > 0
        )


def create_session(token_hash: str, user_id: int, expires_at: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now(),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash, user_id, expires_at)
        )


def get_session_user(token_hash: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = ? AND s.expires_at > ?",
            (token_hash, _now()),
        ).fetchone()
    return dict(row) if row else None


def delete_session(token_hash: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
