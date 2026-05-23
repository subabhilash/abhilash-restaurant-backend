from __future__ import annotations

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    count: int
    total_pages: int
    current_page: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[T]


class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}
