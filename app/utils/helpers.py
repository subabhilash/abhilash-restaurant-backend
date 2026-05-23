from __future__ import annotations

import math
import re
from typing import Any, Callable, Optional, TypeVar

from fastapi import Request
from sqlalchemy.orm import Query

from app.schemas.common import PaginatedResponse

T = TypeVar("T")


def paginate(query: Query, page: int, page_size: int, serializer: Callable) -> PaginatedResponse:
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    total = query.count()
    total_pages = math.ceil(total / page_size) if total else 1
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        count=total,
        total_pages=total_pages,
        current_page=page,
        next=None,
        previous=None,
        results=[serializer(item) for item in items],
    )


def generate_slug(name: str, db: Any) -> str:
    from app.models.restaurant import Restaurant

    base = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    base = re.sub(r"[\s_-]+", "-", base)
    slug = base[:200]
    suffix = 0
    while db.query(Restaurant).filter_by(slug=slug).first():
        suffix += 1
        slug = f"{base[:195]}-{suffix}"
    return slug


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def log_activity(
    db: Any,
    action: str,
    user_id: Optional[int] = None,
    restaurant_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    """Write an audit entry to activity_logs. Swallows all errors — never blocks the caller."""
    try:
        from app.models.activity import ActivityLog
        db.add(ActivityLog(
            user_id=user_id,
            restaurant_id=restaurant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            log_data=metadata or {},
            ip_address=ip,
        ))
        db.commit()  # always commit so logs persist even if caller doesn't
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
