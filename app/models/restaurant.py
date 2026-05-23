from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SUBSCRIPTION_PLANS = ("free", "starter", "professional", "enterprise")
SUBSCRIPTION_STATUSES = ("trial", "active", "inactive", "expired", "cancelled")


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False, index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Branding
    logo: Mapped[Optional[str]] = mapped_column(String(500))

    # Business info
    description: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    state: Mapped[str] = mapped_column(String(100), default="")
    country: Mapped[str] = mapped_column(String(100), default="IN")

    # Operational
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00)
    service_charge_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00)

    # Feature flags (flat — no separate settings table)
    allow_online_ordering: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_accept_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    kitchen_display_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Subscription (denormalized from subscriptions table for fast reads)
    subscription_plan: Mapped[str] = mapped_column(String(20), default="free", index=True)
    subscription_status: Mapped[str] = mapped_column(String(20), default="trial")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[Optional[User]] = relationship(  # noqa: F821
        "User", foreign_keys=[owner_id], primaryjoin="Restaurant.owner_id == User.id"
    )
    staff: Mapped[List[User]] = relationship(  # noqa: F821
        "User", back_populates="restaurant", foreign_keys="User.restaurant_id"
    )
    tables: Mapped[List[RestaurantTable]] = relationship(  # noqa: F821
        "RestaurantTable", back_populates="restaurant", cascade="all, delete-orphan"
    )
    categories: Mapped[List[Category]] = relationship(  # noqa: F821
        "Category", back_populates="restaurant", cascade="all, delete-orphan"
    )
    orders: Mapped[List[Order]] = relationship(  # noqa: F821
        "Order", back_populates="restaurant", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List[Subscription]] = relationship(  # noqa: F821
        "Subscription", back_populates="restaurant", cascade="all, delete-orphan"
    )

    @property
    def is_subscription_active(self) -> bool:
        return self.subscription_status in ("trial", "active")

    def __repr__(self) -> str:
        return f"<Restaurant {self.name} [{self.subscription_plan}]>"
