from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin, require_super_admin
from app.database import get_db
from app.models.order import Order
from app.models.restaurant import Restaurant
from app.models.user import User

router = APIRouter()


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start() -> datetime:
    return _today_start() - timedelta(days=6)


def _daily_breakdown(db: Session, restaurant_id: Optional[int] = None) -> List[dict]:
    """Last 7 days order counts and revenue — single GROUP BY query, not 7 queries."""
    from sqlalchemy import cast, Date as SADate
    week_ago = _today_start() - timedelta(days=6)

    q = db.query(
        cast(Order.created_at, SADate).label("day"),
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
    ).filter(
        Order.created_at >= week_ago,
        Order.deleted_at.is_(None),
    )
    if restaurant_id:
        q = q.filter(Order.restaurant_id == restaurant_id)

    rows = q.group_by(cast(Order.created_at, SADate)).all()
    by_date = {str(r.day): (r.orders, float(r.revenue)) for r in rows}

    # Build a full 7-day series, filling gaps with zeros
    results = []
    for days_ago in range(6, -1, -1):
        day = (_today_start() - timedelta(days=days_ago)).date()
        key = str(day)
        orders, revenue = by_date.get(key, (0, 0.0))
        results.append({
            "date": key,
            "day": day.strftime("%a"),
            "orders": orders,
            "revenue": revenue,
        })
    return results


@router.get("/platform")
def platform_analytics(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Platform-wide stats for the super admin dashboard."""
    today = _today_start()

    total_restaurants = db.query(func.count(Restaurant.id)).scalar() or 0
    active_restaurants = db.query(func.count(Restaurant.id)).filter(Restaurant.is_active == True).scalar() or 0
    total_users = db.query(func.count(User.id)).filter(User.role != "super_admin").scalar() or 0
    total_orders = db.query(func.count(Order.id)).filter(Order.deleted_at.is_(None)).scalar() or 0

    # Today's orders
    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= today, Order.deleted_at.is_(None)
    ).scalar() or 0

    # Subscription breakdown
    plan_counts = db.query(
        Restaurant.subscription_plan, func.count(Restaurant.id)
    ).group_by(Restaurant.subscription_plan).all()
    plans = {row[0]: row[1] for row in plan_counts}

    # Total revenue (paid orders)
    total_revenue = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(Order.payment_status == "paid", Order.deleted_at.is_(None)).scalar() or 0

    # Today's revenue
    today_revenue = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.payment_status == "paid",
        Order.created_at >= today,
        Order.deleted_at.is_(None),
    ).scalar() or 0

    # Orders by status
    status_counts = db.query(
        Order.status, func.count(Order.id)
    ).filter(Order.deleted_at.is_(None)).group_by(Order.status).all()

    # 7-day trend
    weekly_data = _daily_breakdown(db)

    return {
        "total_restaurants": total_restaurants,
        "active_restaurants": active_restaurants,
        "inactive_restaurants": total_restaurants - active_restaurants,
        "total_users": total_users,
        "total_orders": total_orders,
        "today_orders": today_orders,
        "total_revenue": float(total_revenue),
        "today_revenue": float(today_revenue),
        "subscription_plans": plans,
        "order_statuses": {row[0]: row[1] for row in status_counts},
        "weekly_data": weekly_data,
    }


@router.get("/restaurant")
def restaurant_analytics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Restaurant-specific analytics for the restaurant admin dashboard."""
    rid = current_user.restaurant_id
    if not rid:
        return {}

    today = _today_start()

    total_orders = db.query(func.count(Order.id)).filter(
        Order.restaurant_id == rid, Order.deleted_at.is_(None)
    ).scalar() or 0

    today_orders = db.query(func.count(Order.id)).filter(
        Order.restaurant_id == rid,
        Order.created_at >= today,
        Order.deleted_at.is_(None),
    ).scalar() or 0

    open_orders = db.query(func.count(Order.id)).filter(
        Order.restaurant_id == rid,
        Order.status.in_(["pending", "confirmed", "preparing", "ready"]),
        Order.deleted_at.is_(None),
    ).scalar() or 0

    total_revenue = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.restaurant_id == rid,
        Order.payment_status == "paid",
        Order.deleted_at.is_(None),
    ).scalar() or 0

    today_revenue = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.restaurant_id == rid,
        Order.payment_status == "paid",
        Order.created_at >= today,
        Order.deleted_at.is_(None),
    ).scalar() or 0

    staff_count = db.query(func.count(User.id)).filter(
        User.restaurant_id == rid, User.is_active == True
    ).scalar() or 0

    status_counts = db.query(
        Order.status, func.count(Order.id)
    ).filter(
        Order.restaurant_id == rid, Order.deleted_at.is_(None)
    ).group_by(Order.status).all()

    weekly_data = _daily_breakdown(db, restaurant_id=rid)

    return {
        "total_orders": total_orders,
        "today_orders": today_orders,
        "open_orders": open_orders,
        "total_revenue": float(total_revenue),
        "today_revenue": float(today_revenue),
        "staff_count": staff_count,
        "order_statuses": {row[0]: row[1] for row in status_counts},
        "weekly_data": weekly_data,
    }
