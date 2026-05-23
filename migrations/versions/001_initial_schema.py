"""Initial schema — all core tables

Revision ID: 001
Revises:
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM types are auto-created by SQLAlchemy when the first table using them
    # is created via create_table — no need to CREATE TYPE manually.

    # ── restaurants ───────────────────────────────────────────────────────────
    op.create_table(
        "restaurants",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), unique=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger, nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("phone", sa.String(20), server_default=""),
        sa.Column("email", sa.String(255), server_default=""),
        sa.Column("address", sa.Text, server_default=""),
        sa.Column("city", sa.String(100), server_default=""),
        sa.Column("state", sa.String(100), server_default=""),
        sa.Column("country", sa.String(100), server_default="IN"),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("tax_rate", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("service_charge_rate", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("allow_online_ordering", sa.Boolean, server_default="true"),
        sa.Column("auto_accept_orders", sa.Boolean, server_default="false"),
        sa.Column("kitchen_display_enabled", sa.Boolean, server_default="true"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_restaurants_slug", "restaurants", ["slug"])
    op.create_index("ix_restaurants_is_active", "restaurants", ["is_active"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", sa.Enum("admin", "kitchen", "waiter", name="user_role"), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_restaurant_id", "users", ["restaurant_id"])
    op.create_index("ix_users_restaurant_role", "users", ["restaurant_id", "role"])
    op.create_index("ix_users_restaurant_active", "users", ["restaurant_id", "is_active"])

    # Add FK from restaurants.owner_id → users.id (deferred to avoid circular)
    op.create_foreign_key(
        "fk_restaurants_owner_id", "restaurants", "users", ["owner_id"], ["id"], ondelete="SET NULL"
    )

    # ── refresh_tokens ────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, server_default="false"),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # ── restaurant_tables ─────────────────────────────────────────────────────
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_number", sa.String(10), nullable=False),
        sa.Column("capacity", sa.SmallInteger, server_default="4"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("qr_token", sa.String(64), unique=True, nullable=False),
        sa.Column("location_description", sa.String(100), server_default=""),
        sa.Column("occupied_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_freed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "table_number", name="uq_table_restaurant_number"),
    )
    op.create_index("ix_restaurant_tables_restaurant_id", "restaurant_tables", ["restaurant_id"])
    op.create_index("ix_restaurant_tables_qr_token", "restaurant_tables", ["qr_token"])

    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("display_order", sa.SmallInteger, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "name", name="uq_category_restaurant_name"),
    )
    op.create_index("ix_categories_restaurant_id", "categories", ["restaurant_id"])

    # ── menu_items ────────────────────────────────────────────────────────────
    op.create_table(
        "menu_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.BigInteger, sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("display_order", sa.SmallInteger, server_default="0"),
        sa.Column("is_available", sa.Boolean, server_default="true"),
        sa.Column("preparation_time_minutes", sa.SmallInteger, server_default="15"),
        sa.Column("calories", sa.Integer, nullable=True),
        sa.Column("allergens", sa.JSON, server_default="[]"),
        sa.Column("dietary_tags", sa.JSON, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_menu_items_restaurant_id", "menu_items", ["restaurant_id"])
    op.create_index("ix_menu_items_restaurant_available", "menu_items", ["restaurant_id", "is_available"])

    # ── orders ────────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.BigInteger, sa.ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_number", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(200), server_default=""),
        sa.Column("customer_phone", sa.String(20), server_default=""),
        sa.Column("order_type", sa.Enum("dine_in", "takeout", "delivery", name="order_type"), server_default="dine_in"),
        sa.Column("status", sa.Enum("pending", "confirmed", "preparing", "ready", "served", "completed", "cancelled", name="order_status"), server_default="pending"),
        sa.Column("payment_status", sa.Enum("unpaid", "paid", "partially_paid", "refunded", name="payment_status"), server_default="unpaid"),
        sa.Column("special_instructions", sa.Text, server_default=""),
        sa.Column("subtotal", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("service_charge", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preparing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_restaurant_id", "orders", ["restaurant_id"])
    op.create_index("ix_orders_order_number", "orders", ["order_number"])
    op.create_index("ix_orders_restaurant_status", "orders", ["restaurant_id", "status"])
    op.create_index("ix_orders_restaurant_created", "orders", ["restaurant_id", "created_at"])
    op.create_index("ix_orders_restaurant_payment", "orders", ["restaurant_id", "payment_status"])

    # ── order_items ───────────────────────────────────────────────────────────
    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("menu_item_id", sa.BigInteger, sa.ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("menu_item_name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.SmallInteger, nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("special_instructions", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # ── kitchen_tickets ───────────────────────────────────────────────────────
    op.create_table(
        "kitchen_tickets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("assigned_to", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Enum("pending", "in_progress", "ready", "delivered", "cancelled", name="ticket_status"), server_default="pending"),
        sa.Column("priority", sa.Enum("low", "normal", "high", "urgent", name="ticket_priority"), server_default="normal"),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_kitchen_tickets_restaurant_id", "kitchen_tickets", ["restaurant_id"])
    op.create_index("ix_kitchen_tickets_restaurant_status", "kitchen_tickets", ["restaurant_id", "status"])

    # ── activity_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.BigInteger, nullable=True),
        sa.Column("log_data", sa.JSON, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_restaurant_id", "activity_logs", ["restaurant_id"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("activity_logs")
    op.drop_table("kitchen_tickets")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("menu_items")
    op.drop_table("categories")
    op.drop_table("restaurant_tables")
    op.drop_table("refresh_tokens")
    op.drop_constraint("fk_restaurants_owner_id", "restaurants", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("restaurants")
    op.execute("DROP TYPE IF EXISTS ticket_priority")
    op.execute("DROP TYPE IF EXISTS ticket_status")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS order_type")
    op.execute("DROP TYPE IF EXISTS user_role")
