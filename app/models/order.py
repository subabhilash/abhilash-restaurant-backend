from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey,
    Index, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_number: Mapped[str] = mapped_column(String(10), nullable=False)
    capacity: Mapped[int] = mapped_column(SmallInteger, default=4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    location_description: Mapped[str] = mapped_column(String(100), default="")
    # Occupancy tracking
    status: Mapped[str] = mapped_column(
        Enum("available", "occupied", "reserved", name="table_status"),
        default="available",
        index=True,
    )
    occupied_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_freed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    restaurant: Mapped[Restaurant] = relationship(  # noqa: F821
        "Restaurant", back_populates="tables"
    )
    orders: Mapped[List[Order]] = relationship("Order", back_populates="table")
    qr_codes: Mapped[List[TableQRCode]] = relationship(  # noqa: F821
        "TableQRCode", back_populates="table", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("restaurant_id", "table_number", name="uq_table_restaurant_number"),
    )

    @property
    def qr_url(self) -> str:
        from app.config import get_settings
        return f"{get_settings().frontend_url}/order/{self.restaurant.slug}/{self.qr_token}"

    @property
    def active_qr(self) -> Optional[TableQRCode]:  # noqa: F821
        for qr in self.qr_codes:
            if qr.status == "active" and qr.deleted_at is None:
                return qr
        return None


class TableQRCode(Base):
    __tablename__ = "table_qr_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurant_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qr_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    qr_token: Mapped[str] = mapped_column(String(96), unique=True, nullable=False, index=True)
    qr_url: Mapped[str] = mapped_column(String(700), default="")
    status: Mapped[str] = mapped_column(
        Enum("active", "disabled", "rotated", "expired", name="qr_code_status"),
        default="active",
        index=True,
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_role: Mapped[str] = mapped_column(String(50), default="")
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scan_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    table: Mapped[RestaurantTable] = relationship("RestaurantTable", back_populates="qr_codes")
    restaurant: Mapped[Restaurant] = relationship("Restaurant")  # noqa: F821
    creator: Mapped[Optional[User]] = relationship("User", foreign_keys=[created_by])  # noqa: F821

    __table_args__ = (
        Index("ix_table_qr_codes_restaurant_status", "restaurant_id", "status"),
        Index("ix_table_qr_codes_table_status", "table_id", "status"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="")
    customer_phone: Mapped[str] = mapped_column(String(20), default="")

    order_type: Mapped[str] = mapped_column(
        Enum("dine_in", "takeout", "delivery", name="order_type"), default="dine_in"
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "confirmed", "preparing", "ready",
            "served", "completed", "cancelled", name="order_status",
        ),
        default="pending",
        index=True,
    )
    payment_status: Mapped[str] = mapped_column(
        Enum("unpaid", "paid", "partially_paid", "refunded", name="payment_status"),
        default="unpaid",
        index=True,
    )

    special_instructions: Mapped[str] = mapped_column(Text, default="")

    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    service_charge: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    preparing_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    served_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    restaurant: Mapped[Restaurant] = relationship("Restaurant", back_populates="orders")  # noqa: F821
    table: Mapped[Optional[RestaurantTable]] = relationship("RestaurantTable", back_populates="orders")
    items: Mapped[List[OrderItem]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[List[OrderStatusHistory]] = relationship(  # noqa: F821
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan"
    )
    created_by_user: Mapped[Optional[User]] = relationship(  # noqa: F821
        "User", back_populates="created_orders", foreign_keys=[created_by]
    )
    kitchen_ticket: Mapped[Optional[KitchenTicket]] = relationship(  # noqa: F821
        "KitchenTicket", back_populates="order", uselist=False
    )

    __table_args__ = (
        Index("ix_orders_restaurant_status", "restaurant_id", "status"),
        Index("ix_orders_restaurant_created", "restaurant_id", "created_at"),
        Index("ix_orders_restaurant_payment", "restaurant_id", "payment_status"),
    )

    _TRANSITIONS: dict = {
        "pending":   {"confirmed", "cancelled"},
        "confirmed": {"preparing", "cancelled"},
        "preparing": {"ready", "cancelled"},
        "ready":     {"served", "preparing"},
        "served":    {"completed", "ready"},
        "completed": set(),
        "cancelled": set(),
    }

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self._TRANSITIONS.get(self.status, set())


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False
    )
    menu_item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    special_instructions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship("Order", back_populates="items")
    menu_item: Mapped[MenuItem] = relationship("MenuItem")  # noqa: F821


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(30), default="staff")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship("Order", back_populates="status_history")

    __table_args__ = (
        Index("ix_order_status_history_restaurant_created", "restaurant_id", "created_at"),
    )
