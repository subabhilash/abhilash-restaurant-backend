"""Add missing soft delete columns.

Revision ID: 006
Revises: 005
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name in ("users", "categories", "menu_items"):
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
            )
        )
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS ix_{table_name}_deleted_at "
                f"ON {table_name} (deleted_at)"
            )
        )


def downgrade() -> None:
    for table_name in ("menu_items", "categories", "users"):
        op.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table_name}_deleted_at"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS deleted_at"))
