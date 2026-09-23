from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WaiterCall(Base):
    __tablename__ = "waiter_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurant_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_session_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("customer_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    reason: Mapped[str] = mapped_column(String(120), default="waiter")
    notes: Mapped[str] = mapped_column(Text, default="")
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    history: Mapped[list[WaiterCallStatusHistory]] = relationship(
        "WaiterCallStatusHistory", back_populates="waiter_call", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_waiter_calls_restaurant_status", "restaurant_id", "status"),
    )


class WaiterCallStatusHistory(Base):
    __tablename__ = "waiter_call_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waiter_call_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("waiter_calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    waiter_call: Mapped[WaiterCall] = relationship("WaiterCall", back_populates="history")
