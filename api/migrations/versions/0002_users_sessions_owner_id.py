"""users, sessions, tasks.owner_id

절차 (DATA-MIGRATION-PLAN.md 와 같은 순서)
 1. users, sessions 표를 만든다.
 2. 기존 Task가 있으면 주인 계정 하나를 만든다. 비밀번호 없이 만들어 로그인은 못 한다.
    같은 이메일로 가입하면 그 계정을 넘겨받는다.
 3. owner_id NOT NULL 이 붙은 새 표(tasks_new)를 만들고 모든 행을 주인에게 붙여 옮긴다.
 4. 행 수가 같은지 확인한 뒤에야 옛 표를 지우고 새 표 이름을 tasks 로 바꾼다.

Revision ID: 0002
Revises: 0001
"""
import os

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LEGACY_OWNER_EMAIL = os.environ.get("TASKFLOW_LEGACY_OWNER_EMAIL", "owner@taskflow.local").strip().lower()

TASK_COLUMNS = "id, title, description, due_date, priority, status, created_at"

TASKS_DDL = """
CREATE TABLE {name} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    {owner}
    title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT,
    due_date    TEXT,
    priority    TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('urgent', 'normal', 'low')),
    status      TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
)
"""


def _count(conn, table: str) -> int:
    return conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()


def _swap_tasks(conn, new_ddl: str, select_cols: str, insert_cols: str) -> None:
    before = _count(conn, "tasks")
    seq = conn.execute(sa.text("SELECT seq FROM sqlite_sequence WHERE name = 'tasks'")).scalar()
    conn.execute(sa.text(new_ddl))
    conn.execute(sa.text(f"INSERT INTO tasks_new ({insert_cols}) SELECT {select_cols} FROM tasks"))
    if _count(conn, "tasks_new") != before:
        raise RuntimeError("tasks 행 수가 달라져 중단합니다. 옛 tasks 표는 그대로 있습니다.")
    conn.execute(sa.text("DROP TABLE tasks"))
    conn.execute(sa.text("ALTER TABLE tasks_new RENAME TO tasks"))
    if seq is not None:  # 삭제된 번호를 다시 쓰지 않는다 (DATA-MODEL id 규칙)
        conn.execute(sa.text("UPDATE sqlite_sequence SET seq = :s WHERE name = 'tasks'"), {"s": seq})


def upgrade() -> None:
    conn = op.get_bind()

    op.execute(
        """
        CREATE TABLE users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL UNIQUE CHECK (length(trim(email)) > 0),
            password_hash TEXT,
            created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            expires_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_sessions_user_id ON sessions (user_id)")

    owner_id = 0  # Task가 없으면 옮길 행도 없으니 값은 쓰이지 않는다
    if _count(conn, "tasks") > 0:
        conn.execute(sa.text("INSERT INTO users (email, password_hash) VALUES (:e, NULL)"), {"e": LEGACY_OWNER_EMAIL})
        owner_id = conn.execute(sa.text("SELECT id FROM users WHERE email = :e"), {"e": LEGACY_OWNER_EMAIL}).scalar_one()

    _swap_tasks(
        conn,
        TASKS_DDL.format(name="tasks_new", owner="owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"),
        select_cols=TASK_COLUMNS.replace("id, ", f"id, {int(owner_id)}, ", 1),
        insert_cols=TASK_COLUMNS.replace("id, ", "id, owner_id, ", 1),
    )
    op.execute("CREATE INDEX ix_tasks_owner_id ON tasks (owner_id)")


def downgrade() -> None:
    conn = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_tasks_owner_id")
    _swap_tasks(conn, TASKS_DDL.format(name="tasks_new", owner=""), TASK_COLUMNS, TASK_COLUMNS)
    op.execute("DROP TABLE sessions")
    op.execute("DROP TABLE users")
