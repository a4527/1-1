"""baseline tasks

M2 이전에 앱이 직접 만들던 tasks 표를 alembic 이력의 출발점으로 삼는다.
이미 tasks 표가 있는 DB에서는 아무것도 바꾸지 않는다.

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
    )


def downgrade() -> None:
    # 기준선이라 되돌리지 않는다. 기존 Task를 지우지 않기 위해서다.
    pass
