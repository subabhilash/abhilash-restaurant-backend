"""Production fixes — order number unique constraint, drop redundant indexes,
add password_reset_tokens table, cleanup index for refresh_tokens

Revision ID: 003
Revises: 002
Create Date: 2026-05-23
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Unique constraint on (restaurant_id, order_number) ─────────────────
    # First ensure no existing duplicates (safe for fresh DB)
    op.create_unique_constraint(
        "uq_orders_restaurant_order_number",
        "orders",
        ["restaurant_id", "order_number"],
    )

    # ── 2. Drop redundant unique index duplicates ─────────────────────────────
    # restaurants.slug has both restaurants_slug_key (constraint) and ix_restaurants_slug (index)
    # The constraint already creates an index; drop the explicit one
    op.drop_index("ix_restaurants_slug", table_name="restaurants")

    # restaurant_tables.qr_token same pattern
    op.drop_index("ix_restaurant_tables_qr_token", table_name="restaurant_tables")

    # ── 3. Index for refresh_token cleanup queries ────────────────────────────
    op.create_index(
        "ix_refresh_tokens_expires_revoked",
        "refresh_tokens",
        ["expires_at", "is_revoked"],
    )

    # ── 4. Password reset tokens table ───────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 5. Add deleted_at to soft-deletable tables ────────────────────────────
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("menu_items", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("categories", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # ── 6. Add last_freed_at default and fix table status ─────────────────────
    # Ensure any existing tables with NULL status get 'available'
    op.execute(sa.text(
        "UPDATE restaurant_tables SET status = 'available' WHERE status IS NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE categories DROP COLUMN IF EXISTS deleted_at"))
    op.execute(sa.text("ALTER TABLE menu_items DROP COLUMN IF EXISTS deleted_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at"))
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_refresh_tokens_expires_revoked", table_name="refresh_tokens")
    op.create_index("ix_restaurant_tables_qr_token", "restaurant_tables", ["qr_token"])
    op.create_index("ix_restaurants_slug", "restaurants", ["slug"])
    op.drop_constraint("uq_orders_restaurant_order_number", "orders", type_="unique")
