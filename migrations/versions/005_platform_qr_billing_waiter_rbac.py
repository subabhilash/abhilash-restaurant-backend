"""Platform QR, RBAC, waiter, billing, and session tables.

Revision ID: 005
Revises: 004
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    qr_status = sa.Enum("active", "disabled", "rotated", "expired", name="qr_code_status")

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(40), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_monthly", sa.Numeric(10, 2), server_default="0"),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("features", sa.Text, server_default=""),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "subscription_payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.BigInteger, sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("status", sa.String(20), server_default="paid"),
        sa.Column("provider", sa.String(50), server_default=""),
        sa.Column("reference", sa.String(120), server_default=""),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_payments_restaurant_id", "subscription_payments", ["restaurant_id"])
    op.create_index("ix_subscription_payments_subscription_id", "subscription_payments", ["subscription_id"])
    op.create_index("ix_subscription_payments_status", "subscription_payments", ["status"])

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "name", name="uq_roles_restaurant_name"),
    )
    op.create_index("ix_roles_restaurant_id", "roles", ["restaurant_id"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(120), unique=True, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.BigInteger, sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "role_id", "restaurant_id", name="uq_user_roles_scope"),
    )
    op.create_index("ix_user_roles_restaurant_id", "user_roles", ["restaurant_id"])
    op.create_index("ix_user_roles_user_restaurant", "user_roles", ["user_id", "restaurant_id"])

    op.create_table(
        "table_qr_codes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.BigInteger, sa.ForeignKey("restaurant_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qr_id", sa.String(64), unique=True, nullable=False),
        sa.Column("qr_token", sa.String(96), unique=True, nullable=False),
        sa.Column("qr_url", sa.String(700), server_default=""),
        sa.Column("status", qr_status, server_default="active", nullable=False),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_role", sa.String(50), server_default=""),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_count", sa.Integer, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_table_qr_codes_restaurant_id", "table_qr_codes", ["restaurant_id"])
    op.create_index("ix_table_qr_codes_table_id", "table_qr_codes", ["table_id"])
    op.create_index("ix_table_qr_codes_qr_id", "table_qr_codes", ["qr_id"])
    op.create_index("ix_table_qr_codes_qr_token", "table_qr_codes", ["qr_token"])
    op.create_index("ix_table_qr_codes_deleted_at", "table_qr_codes", ["deleted_at"])
    op.create_index("ix_table_qr_codes_restaurant_status", "table_qr_codes", ["restaurant_id", "status"])
    op.create_index("ix_table_qr_codes_table_status", "table_qr_codes", ["table_id", "status"])
    op.execute(sa.text(
        """
        INSERT INTO table_qr_codes (
            restaurant_id, table_id, qr_id, qr_token, qr_url, status, created_by_role, scan_count
        )
        SELECT
            restaurant_id,
            id,
            'qr_' || md5(random()::text || clock_timestamp()::text || id::text),
            qr_token,
            '',
            'active',
            'migration',
            0
        FROM restaurant_tables
        WHERE qr_token IS NOT NULL
        """
    ))

    op.create_table(
        "customer_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.BigInteger, sa.ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True),
        sa.Column("qr_code_id", sa.BigInteger, sa.ForeignKey("table_qr_codes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_token", sa.String(96), unique=True, nullable=False),
        sa.Column("customer_name", sa.String(200), server_default=""),
        sa.Column("customer_phone", sa.String(20), server_default=""),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customer_sessions_restaurant_id", "customer_sessions", ["restaurant_id"])
    op.create_index("ix_customer_sessions_table_id", "customer_sessions", ["table_id"])
    op.create_index("ix_customer_sessions_qr_code_id", "customer_sessions", ["qr_code_id"])
    op.create_index("ix_customer_sessions_session_token", "customer_sessions", ["session_token"])
    op.create_index("ix_customer_sessions_status", "customer_sessions", ["status"])

    op.create_table(
        "carts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_session_id", sa.BigInteger, sa.ForeignKey("customer_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_carts_restaurant_id", "carts", ["restaurant_id"])
    op.create_index("ix_carts_customer_session_id", "carts", ["customer_session_id"])
    op.create_index("ix_carts_status", "carts", ["status"])

    op.create_table(
        "cart_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("cart_id", sa.BigInteger, sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("menu_item_id", sa.BigInteger, sa.ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer, server_default="1"),
        sa.Column("special_instructions", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("cart_id", "menu_item_id", name="uq_cart_items_cart_menu_item"),
    )

    op.create_table(
        "qr_scan_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.BigInteger, sa.ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True),
        sa.Column("qr_code_id", sa.BigInteger, sa.ForeignKey("table_qr_codes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_session_id", sa.BigInteger, sa.ForeignKey("customer_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_qr_scan_events_restaurant_id", "qr_scan_events", ["restaurant_id"])
    op.create_index("ix_qr_scan_events_table_id", "qr_scan_events", ["table_id"])
    op.create_index("ix_qr_scan_events_qr_code_id", "qr_scan_events", ["qr_code_id"])
    op.create_index("ix_qr_scan_events_customer_session_id", "qr_scan_events", ["customer_session_id"])
    op.create_index("ix_qr_scan_events_restaurant_created", "qr_scan_events", ["restaurant_id", "created_at"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(30), server_default="staff"),
        sa.Column("note", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_status_history_restaurant_id", "order_status_history", ["restaurant_id"])
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])
    op.create_index("ix_order_status_history_restaurant_created", "order_status_history", ["restaurant_id", "created_at"])

    op.create_table(
        "kitchen_ticket_status_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.BigInteger, sa.ForeignKey("kitchen_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_kitchen_ticket_status_history_restaurant_id", "kitchen_ticket_status_history", ["restaurant_id"])
    op.create_index("ix_kitchen_ticket_status_history_ticket_id", "kitchen_ticket_status_history", ["ticket_id"])
    op.create_index("ix_kitchen_ticket_status_history_restaurant_created", "kitchen_ticket_status_history", ["restaurant_id", "created_at"])

    op.create_table(
        "waiter_calls",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.BigInteger, sa.ForeignKey("restaurant_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_session_id", sa.BigInteger, sa.ForeignKey("customer_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("reason", sa.String(120), server_default="waiter"),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_waiter_calls_restaurant_id", "waiter_calls", ["restaurant_id"])
    op.create_index("ix_waiter_calls_table_id", "waiter_calls", ["table_id"])
    op.create_index("ix_waiter_calls_customer_session_id", "waiter_calls", ["customer_session_id"])
    op.create_index("ix_waiter_calls_status", "waiter_calls", ["status"])
    op.create_index("ix_waiter_calls_restaurant_status", "waiter_calls", ["restaurant_id", "status"])

    op.create_table(
        "waiter_call_status_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("waiter_call_id", sa.BigInteger, sa.ForeignKey("waiter_calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_waiter_call_status_history_waiter_call_id", "waiter_call_status_history", ["waiter_call_id"])

    op.create_table(
        "taxes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("rate", sa.Numeric(5, 2), server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "name", name="uq_taxes_restaurant_name"),
    )
    op.create_index("ix_taxes_restaurant_id", "taxes", ["restaurant_id"])

    op.create_table(
        "discounts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("discount_type", sa.String(20), server_default="fixed"),
        sa.Column("value", sa.Numeric(10, 2), server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_discounts_restaurant_id", "discounts", ["restaurant_id"])

    op.create_table(
        "payment_methods",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_methods_restaurant_id", "payment_methods", ["restaurant_id"])

    op.create_table(
        "bills",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bill_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("subtotal", sa.Numeric(10, 2), server_default="0"),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0"),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0"),
        sa.Column("service_charge", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total_amount", sa.Numeric(10, 2), server_default="0"),
        sa.Column("paid_amount", sa.Numeric(10, 2), server_default="0"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "bill_number", name="uq_bills_restaurant_bill_number"),
    )
    op.create_index("ix_bills_restaurant_id", "bills", ["restaurant_id"])
    op.create_index("ix_bills_status", "bills", ["status"])
    op.create_index("ix_bills_deleted_at", "bills", ["deleted_at"])
    op.create_index("ix_bills_restaurant_status", "bills", ["restaurant_id", "status"])

    op.create_table(
        "bill_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("bill_id", sa.BigInteger, sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", sa.BigInteger, sa.ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.BigInteger, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total_price", sa.Numeric(10, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.BigInteger, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bill_id", sa.BigInteger, sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method_id", sa.BigInteger, sa.ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="paid"),
        sa.Column("reference", sa.String(120), server_default=""),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payments_restaurant_id", "payments", ["restaurant_id"])
    op.create_index("ix_payments_status", "payments", ["status"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("bill_items")
    op.drop_table("bills")
    op.drop_table("payment_methods")
    op.drop_table("discounts")
    op.drop_table("taxes")
    op.drop_table("waiter_call_status_history")
    op.drop_table("waiter_calls")
    op.drop_table("kitchen_ticket_status_history")
    op.drop_table("order_status_history")
    op.drop_table("qr_scan_events")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("customer_sessions")
    op.drop_table("table_qr_codes")
    op.drop_table("subscription_payments")
    op.drop_table("subscription_plans")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.execute("DROP TYPE IF EXISTS qr_code_status")
