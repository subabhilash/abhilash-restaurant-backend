from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WaiterCallCreate(BaseModel):
    table_id: int = Field(gt=0)
    reason: str = Field(default="waiter", max_length=120)
    notes: str = Field(default="", max_length=500)


class PublicWaiterCallCreate(BaseModel):
    qr_token: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="waiter", max_length=120)
    notes: str = Field(default="", max_length=500)


class WaiterCallUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20)
    assigned_to: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class WaiterCallResponse(BaseModel):
    id: int
    restaurant_id: int
    table_id: int
    customer_session_id: Optional[int]
    assigned_to: Optional[int]
    status: str
    reason: str
    notes: str
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
