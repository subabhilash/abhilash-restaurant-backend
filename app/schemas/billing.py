from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BillItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    unit_price: float
    total_price: float

    model_config = {"from_attributes": True}


class BillCreate(BaseModel):
    order_id: int = Field(gt=0)


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_method_id: Optional[int] = None
    reference: str = ""
    notes: str = ""


class BillResponse(BaseModel):
    id: int
    restaurant_id: int
    order_id: int
    bill_number: str
    status: str
    subtotal: float
    tax_amount: float
    discount_amount: float
    service_charge: float
    total_amount: float
    paid_amount: float
    closed_at: Optional[datetime]
    items: List[BillItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
