"""Kitchen stations table, station FK on tickets, orders soft delete

Revision ID: 004
Revises: 003
Create Date: 2026-05-23
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. kitchen_stations table ─────────────────────────────────────────────
    op.create_table(
        "kitchen_stations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "restaurant_id",
            sa.BigInteger,
            sa.ForeignKey("restaurants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_color", sa.String(7), server_default="#3B82F6"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("display_order", sa.SmallInteger, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("restaurant_id", "name", name="uq_station_restaurant_name"),
    )
    # Note: ix_kitchen_stations_restaurant_id created inline via index=True on the column

    # ── 2. Add station_id FK to kitchen_tickets ───────────────────────────────
    op.add_column(
        "kitchen_tickets",
        sa.Column(
            "station_id",
            sa.BigInteger,
            sa.ForeignKey("kitchen_stations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_kitchen_tickets_station_id", "kitchen_tickets", ["station_id"]
    )

    # ── 3. Soft delete for orders ─────────────────────────────────────────────
    op.add_column(
        "orders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_orders_deleted_at", "orders", ["deleted_at"])

    # ── 4. Soft delete for order_items ────────────────────────────────────────
    op.add_column(
        "order_items",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_items", "deleted_at")
    op.drop_index("ix_orders_deleted_at", table_name="orders")
    op.drop_column("orders", "deleted_at")
    op.drop_index("ix_kitchen_tickets_station_id", table_name="kitchen_tickets")
    op.drop_column("kitchen_tickets", "station_id")
    op.drop_table("kitchen_stations")  # index dropped with table
