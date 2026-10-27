"""priority 값을 LOW/NORMAL/HIGH 로 바꾼다

절차
 1. CHECK 가 LOW/NORMAL/HIGH 인 새 표(tasks_new)를 만들고 모든 행을 옮긴다.
    low -> LOW, normal -> NORMAL, urgent -> HIGH. 다른 열의 값은 그대로 옮긴다.
 2. 행 수가 같은지 확인한 뒤에야 옛 표를 지우고 새 표 이름을 tasks 로 바꾼다.
 3. ix_tasks_owner_id 를 다시 만든다.

되돌리기는 없다. 실제 DB에 적용하기 전에 백업하고, 되돌릴 때는 백업 파일로 복원한다.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TASKS_DDL = """
CREATE TABLE tasks_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT,
    due_date    TEXT,
    priority    TEXT NOT NULL DEFAULT 'NORMAL' CHECK (priority IN ('LOW', 'NORMAL', 'HIGH')),
    status      TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
)
"""

PRIORITY_MAP = "CASE priority WHEN 'low' THEN 'LOW' WHEN 'normal' THEN 'NORMAL' WHEN 'urgent' THEN 'HIGH' END"


def _count(conn, table: str) -> int:
    return conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()


def upgrade() -> None:
    conn = op.get_bind()

    before = _count(conn, "tasks")
    seq = conn.execute(sa.text("SELECT seq FROM sqlite_sequence WHERE name = 'tasks'")).scalar()
    conn.execute(sa.text(TASKS_DDL))
    conn.execute(
        sa.text(
            "INSERT INTO tasks_new (id, owner_id, title, description, due_date, priority, status, created_at)"
            f" SELECT id, owner_id, title, description, due_date, {PRIORITY_MAP}, status, created_at FROM tasks"
        )
    )
    if _count(conn, "tasks_new") != before:
        raise RuntimeError("tasks 행 수가 달라져 중단합니다. 옛 tasks 표는 그대로 있습니다.")
    conn.execute(sa.text("DROP TABLE tasks"))
    conn.execute(sa.text("ALTER TABLE tasks_new RENAME TO tasks"))
    if seq is not None:  # 삭제된 번호를 다시 쓰지 않는다 (DATA-MODEL id 규칙)
        conn.execute(sa.text("UPDATE sqlite_sequence SET seq = :s WHERE name = 'tasks'"), {"s": seq})
    op.execute("CREATE INDEX ix_tasks_owner_id ON tasks (owner_id)")
