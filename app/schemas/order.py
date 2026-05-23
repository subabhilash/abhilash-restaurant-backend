from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

VALID_ORDER_TYPES = {"dine_in", "takeout", "delivery"}
VALID_PAYMENT_STATUSES = {"unpaid", "paid", "partially_paid", "refunded"}


class TableCreate(BaseModel):
    table_number: str = Field(min_length=1, max_length=10, strip_whitespace=True)
    capacity: int = Field(default=4, ge=1, le=100)
    location_description: str = Field(default="", max_length=100)


class TableUpdate(BaseModel):
    table_number: Optional[str] = Field(default=None, min_length=1, max_length=10, strip_whitespace=True)
    capacity: Optional[int] = Field(default=None, ge=1, le=100)
    location_description: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class TableResponse(BaseModel):
    id: int
    restaurant_id: int
    table_number: str
    capacity: int
    is_active: bool
    status: str = "available"
    qr_token: str
    qr_url: str = ""
    location_description: str
    occupied_since: Optional[datetime]
    last_freed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderItemCreate(BaseModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=100)
    special_instructions: str = Field(default="", max_length=500)


class OrderCreate(BaseModel):
    table_id: Optional[int] = Field(default=None, gt=0)
    customer_name: str = Field(default="", max_length=200, strip_whitespace=True)
    customer_phone: str = Field(default="", max_length=20)
    order_type: str = Field(default="dine_in")
    special_instructions: str = Field(default="", max_length=1000)
    items: List[OrderItemCreate] = Field(min_length=1)

    @field_validator("order_type")
    @classmethod
    def valid_order_type(cls, v: str) -> str:
        if v not in VALID_ORDER_TYPES:
            raise ValueError(f"order_type must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}")
        return v


class OrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class OrderPaymentUpdate(BaseModel):
    payment_status: str = Field(min_length=1, max_length=20)

    @field_validator("payment_status")
    @classmethod
    def valid_payment_status(cls, v: str) -> str:
        if v not in VALID_PAYMENT_STATUSES:
            raise ValueError(f"payment_status must be one of: {', '.join(sorted(VALID_PAYMENT_STATUSES))}")
        return v


class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    quantity: int
    unit_price: float
    total_price: float
    special_instructions: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    restaurant_id: int
    order_number: str
    table_id: Optional[int]
    table_number: Optional[str] = None
    customer_name: str
    customer_phone: str
    order_type: str
    status: str
    payment_status: str
    special_instructions: str
    subtotal: float
    tax_amount: float
    service_charge: float
    discount_amount: float
    total_amount: float
    confirmed_at: Optional[datetime]
    preparing_at: Optional[datetime]
    ready_at: Optional[datetime]
    served_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    items: List[OrderItemResponse] = []
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListItem(BaseModel):
    id: int
    restaurant_id: int  # included so super_admin can identify cross-tenant orders
    order_number: str
    table_number: Optional[str] = None
    customer_name: str
    order_type: str
    status: str
    payment_status: str
    total_amount: float
    item_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicOrderCreate(BaseModel):
    customer_name: str = Field(default="", max_length=200, strip_whitespace=True)
    customer_phone: str = Field(default="", max_length=20)
    special_instructions: str = Field(default="", max_length=1000)
    items: List[OrderItemCreate] = Field(min_length=1)


class PublicOrderTrackResponse(BaseModel):
    id: int
    order_number: str
    status: str
    total_amount: float
    confirmed_at: Optional[datetime]
    preparing_at: Optional[datetime]
    ready_at: Optional[datetime]
    served_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
