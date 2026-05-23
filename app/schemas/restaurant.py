from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RestaurantCreate(BaseModel):
    name: str
    description: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = "IN"
    timezone: str = "UTC"
    currency: str = "INR"
    tax_rate: float = 0.00
    service_charge_rate: float = 0.00
    logo: Optional[str] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    tax_rate: Optional[float] = None
    service_charge_rate: Optional[float] = None
    allow_online_ordering: Optional[bool] = None
    auto_accept_orders: Optional[bool] = None
    kitchen_display_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    logo: Optional[str] = None


class RestaurantResponse(BaseModel):
    id: int
    name: str
    slug: str
    logo: Optional[str]
    description: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    country: str
    timezone: str
    currency: str
    tax_rate: float
    service_charge_rate: float
    allow_online_ordering: bool
    auto_accept_orders: bool
    kitchen_display_enabled: bool
    subscription_plan: str
    subscription_status: str
    is_active: bool
    owner_id: Optional[int]
    owner_email: Optional[str] = None
    staff_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Super Admin: Create restaurant + admin user ───────────────────────────────

class RestaurantOnboardRequest(BaseModel):
    """Super admin creates a new restaurant and its first admin user in one shot."""
    restaurant_name: str
    restaurant_email: str = ""
    restaurant_phone: str = ""
    restaurant_city: str = ""
    restaurant_country: str = "IN"
    # Admin user
    admin_name: str
    admin_email: str
    admin_password: str
    subscription_plan: str = "free"


# ── Subscription management ───────────────────────────────────────────────────

class SubscriptionUpdateRequest(BaseModel):
    plan: str
    status: str = "active"
    expires_at: Optional[datetime] = None
    notes: str = ""


class SubscriptionResponse(BaseModel):
    id: int
    restaurant_id: int
    plan: str
    status: str
    starts_at: datetime
    expires_at: Optional[datetime]
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}
