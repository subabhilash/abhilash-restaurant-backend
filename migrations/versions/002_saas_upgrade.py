"""SaaS upgrade — super_admin role, subscription system, table status

Revision ID: 002
Revises: 001
Create Date: 2026-05-22
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Add super_admin to user_role enum ────────────────────────────────
    conn.execute(sa.text(
        "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin'"
    ))

    # ── 2. Add subscription + branding columns to restaurants ───────────────
    op.add_column("restaurants", sa.Column("logo", sa.String(500), nullable=True))
    op.add_column("restaurants", sa.Column(
        "subscription_plan",
        sa.String(20),
        server_default="free",
        nullable=False,
    ))
    op.add_column("restaurants", sa.Column(
        "subscription_status",
        sa.String(20),
        server_default="trial",
        nullable=False,
    ))
    op.create_index("ix_restaurants_subscription_plan", "restaurants", ["subscription_plan"])

    # ── 3. Add table occupancy status ────────────────────────────────────────
    conn.execute(sa.text(
        "CREATE TYPE table_status AS ENUM ('available', 'occupied', 'reserved')"
    ))
    op.add_column("restaurant_tables", sa.Column(
        "status",
        sa.Enum("available", "occupied", "reserved", name="table_status"),
        server_default="available",
        nullable=False,
    ))
    op.create_index("ix_restaurant_tables_status", "restaurant_tables", ["restaurant_id", "status"])

    # ── 4. Subscriptions table ────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger,
                  sa.ForeignKey("restaurants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger,
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Note: indexes are defined inline in create_table via index=True on the columns


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_index("ix_restaurant_tables_status", table_name="restaurant_tables")
    op.drop_column("restaurant_tables", "status")
    op.execute(sa.text("DROP TYPE IF EXISTS table_status"))
    op.drop_index("ix_restaurants_subscription_plan", table_name="restaurants")
    op.drop_column("restaurants", "subscription_status")
    op.drop_column("restaurants", "subscription_plan")
    op.drop_column("restaurants", "logo")
    # Note: cannot remove enum values in PostgreSQL — super_admin remains in user_role
