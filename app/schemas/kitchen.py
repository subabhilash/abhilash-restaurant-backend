from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Stations ──────────────────────────────────────────────────────────────────

class StationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, strip_whitespace=True)
    display_color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    display_order: int = Field(default=0, ge=0, le=999)


class StationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100, strip_whitespace=True)
    display_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None
    display_order: Optional[int] = Field(default=None, ge=0, le=999)


class StationResponse(BaseModel):
    id: int
    restaurant_id: int
    name: str
    display_color: str
    is_active: bool
    display_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tickets ───────────────────────────────────────────────────────────────────

class KitchenTicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    assigned_to: Optional[int] = None
    station_id: Optional[int] = None


class KitchenOrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class KitchenOrderItemResponse(BaseModel):
    id: int
    menu_item_name: str
    quantity: int
    special_instructions: str

    model_config = {"from_attributes": True}


class KitchenOrderResponse(BaseModel):
    id: int
    order_number: str
    table_number: Optional[str] = None
    order_type: str
    status: str
    special_instructions: str
    items: List[KitchenOrderItemResponse] = []
    confirmed_at: Optional[datetime]
    preparing_at: Optional[datetime]
    ready_at: Optional[datetime]
    created_at: datetime
    elapsed_seconds: int = 0

    model_config = {"from_attributes": True}


class KitchenTicketResponse(BaseModel):
    id: int
    order_id: int
    order_number: str = ""
    table_number: Optional[str] = None
    station_id: Optional[int]
    station_name: Optional[str] = None
    assigned_to: Optional[int]
    assigned_to_name: Optional[str] = None
    status: str
    priority: str
    notes: str
    items: List[KitchenOrderItemResponse] = []
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    prep_time_seconds: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
