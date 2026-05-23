from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, strip_whitespace=True)
    description: str = Field(default="", max_length=500)
    display_order: int = Field(default=0, ge=0, le=9999)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100, strip_whitespace=True)
    description: Optional[str] = Field(default=None, max_length=500)
    display_order: Optional[int] = Field(default=None, ge=0, le=9999)
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: str
    display_order: int
    is_active: bool
    item_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200, strip_whitespace=True)
    description: str = Field(default="", max_length=1000)
    price: float = Field(gt=0, le=999999)
    display_order: int = Field(default=0, ge=0, le=9999)
    preparation_time_minutes: int = Field(default=15, ge=1, le=480)
    calories: Optional[int] = Field(default=None, ge=0, le=99999)
    allergens: List[str] = Field(default_factory=list, max_length=20)
    dietary_tags: List[str] = Field(default_factory=list, max_length=20)


class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = Field(default=None, gt=0)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200, strip_whitespace=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: Optional[float] = Field(default=None, gt=0, le=999999)
    display_order: Optional[int] = Field(default=None, ge=0, le=9999)
    is_available: Optional[bool] = None
    preparation_time_minutes: Optional[int] = Field(default=None, ge=1, le=480)
    calories: Optional[int] = Field(default=None, ge=0, le=99999)
    allergens: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None


class MenuItemResponse(BaseModel):
    id: int
    restaurant_id: int
    category_id: int
    category_name: str = ""
    name: str
    description: str
    price: float
    display_order: int
    is_available: bool
    preparation_time_minutes: int
    calories: Optional[int]
    allergens: List[str]
    dietary_tags: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicMenuItemResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    is_available: bool
    preparation_time_minutes: int
    calories: Optional[int]
    allergens: List[str]
    dietary_tags: List[str]

    model_config = {"from_attributes": True}


class PublicCategoryResponse(BaseModel):
    id: int
    name: str
    description: str
    display_order: int
    items: List[PublicMenuItemResponse]

    model_config = {"from_attributes": True}


class PublicMenuResponse(BaseModel):
    restaurant: dict
    menu: List[PublicCategoryResponse]
