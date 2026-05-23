from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index,
    SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KitchenStation(Base):
    """A logical workstation in the kitchen (e.g. Grill, Salad, Pastry).
    Tickets can be assigned to stations for routing.
    """
    __tablename__ = "kitchen_stations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_color: Mapped[str] = mapped_column(String(7), default="#3B82F6")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tickets: Mapped[List[KitchenTicket]] = relationship(
        "KitchenTicket", back_populates="station", foreign_keys="KitchenTicket.station_id"
    )

    __table_args__ = (
        UniqueConstraint("restaurant_id", "name", name="uq_station_restaurant_name"),
    )

    def __repr__(self) -> str:
        return f"<KitchenStation {self.name}>"


class KitchenTicket(Base):
    """One ticket per order. Updated by kitchen staff via the KDS."""
    __tablename__ = "kitchen_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    station_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("kitchen_stations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        Enum("pending", "in_progress", "ready", "delivered", "cancelled", name="ticket_status"),
        default="pending",
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        Enum("low", "normal", "high", "urgent", name="ticket_priority"),
        default="normal",
    )
    notes: Mapped[str] = mapped_column(Text, default="")

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped[Order] = relationship("Order", back_populates="kitchen_ticket")  # noqa: F821
    station: Mapped[Optional[KitchenStation]] = relationship(
        "KitchenStation", back_populates="tickets", foreign_keys=[station_id]
    )
    assignee: Mapped[Optional[User]] = relationship("User", foreign_keys=[assigned_to])  # noqa: F821

    __table_args__ = (
        Index("ix_kitchen_tickets_restaurant_status", "restaurant_id", "status"),
    )

    @property
    def prep_time_seconds(self) -> Optional[int]:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
