from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user, require_admin, require_restaurant_admin, require_super_admin,
    assert_restaurant_access,
)
from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.restaurant import (
    RestaurantOnboardRequest, RestaurantResponse,
    RestaurantUpdate, SubscriptionResponse, SubscriptionUpdateRequest,
)
from app.utils.helpers import generate_slug, paginate

router = APIRouter()


def _serialize(r: Restaurant, db: Session) -> RestaurantResponse:
    staff_count = db.query(func.count(User.id)).filter(
        User.restaurant_id == r.id, User.is_active == True
    ).scalar() or 0
    owner_email = r.owner.email if r.owner else None
    data = RestaurantResponse.model_validate(r)
    data.staff_count = staff_count
    data.owner_email = owner_email
    return data


# ── Restaurant admin — own restaurant ────────────────────────────────────────

@router.get("/me", response_model=RestaurantResponse)
def get_my_restaurant(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No restaurant assigned")
    r = db.get(Restaurant, current_user.restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return _serialize(r, db)


@router.patch("/me", response_model=RestaurantResponse)
def update_my_restaurant(
    body: RestaurantUpdate,
    current_user: User = Depends(require_restaurant_admin),
    db: Session = Depends(get_db),
):
    r = db.get(Restaurant, current_user.restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _serialize(r, db)


# ── Super admin — all restaurants ────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[RestaurantResponse])
def list_all_restaurants(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = Query(None),
    subscription_plan: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Restaurant)
    if search:
        q = q.filter(Restaurant.name.ilike(f"%{search}%"))
    if subscription_plan:
        q = q.filter(Restaurant.subscription_plan == subscription_plan)
    if is_active is not None:
        q = q.filter(Restaurant.is_active == is_active)
    q = q.order_by(Restaurant.created_at.desc())
    return paginate(q, page, page_size, lambda r: _serialize(r, db))


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
def onboard_restaurant(
    body: RestaurantOnboardRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Super admin creates a new restaurant and its first admin user atomically."""
    from app.services.auth_service import hash_password

    if db.query(User).filter_by(email=body.admin_email.lower().strip()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin email already registered")

    slug = generate_slug(body.restaurant_name, db)
    restaurant = Restaurant(
        name=body.restaurant_name,
        slug=slug,
        email=body.restaurant_email,
        phone=body.restaurant_phone,
        city=body.restaurant_city,
        country=body.restaurant_country,
        subscription_plan=body.subscription_plan,
        subscription_status="active",
    )
    db.add(restaurant)
    db.flush()

    admin = User(
        email=body.admin_email.lower().strip(),
        full_name=body.admin_name,
        password_hash=hash_password(body.admin_password),
        role="admin",
        restaurant_id=restaurant.id,
    )
    db.add(admin)
    db.flush()
    restaurant.owner_id = admin.id

    # Record initial subscription
    db.add(Subscription(
        restaurant_id=restaurant.id,
        plan=body.subscription_plan,
        status="active",
        created_by=current_user.id,
    ))

    db.commit()
    db.refresh(restaurant)
    return _serialize(restaurant, db)


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
def get_restaurant(
    restaurant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_restaurant_access(current_user, restaurant_id)
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return _serialize(r, db)


@router.patch("/{restaurant_id}", response_model=RestaurantResponse)
def update_restaurant(
    restaurant_id: int,
    body: RestaurantUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    assert_restaurant_access(current_user, restaurant_id)
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _serialize(r, db)


@router.delete("/{restaurant_id}", response_model=MessageResponse)
def deactivate_restaurant(
    restaurant_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    r.is_active = False
    db.commit()
    from app.utils.helpers import log_activity
    log_activity(db, action="restaurant.deactivated", user_id=current_user.id,
                 restaurant_id=restaurant_id, resource_type="restaurant", resource_id=restaurant_id)
    return MessageResponse(message=f"Restaurant '{r.name}' deactivated")


@router.patch("/{restaurant_id}/activate", response_model=RestaurantResponse)
def activate_restaurant(
    restaurant_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    r.is_active = True
    db.commit()
    db.refresh(r)
    return _serialize(r, db)


# ── Settings alias endpoints ──────────────────────────────────────────────────

@router.get("/{restaurant_id}/settings", response_model=RestaurantResponse)
def get_settings(restaurant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_restaurant(restaurant_id, current_user, db)


@router.patch("/{restaurant_id}/settings", response_model=RestaurantResponse)
def update_settings(restaurant_id: int, body: RestaurantUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_restaurant(restaurant_id, body, current_user, db)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/{restaurant_id}/stats")
def get_stats(
    restaurant_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    assert_restaurant_access(current_user, restaurant_id)
    from app.models.order import Order
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    staff_count = db.query(func.count(User.id)).filter(User.restaurant_id == r.id, User.is_active == True).scalar() or 0
    total_orders = db.query(func.count(Order.id)).filter(Order.restaurant_id == r.id).scalar() or 0
    open_orders = db.query(func.count(Order.id)).filter(
        Order.restaurant_id == r.id, Order.status.in_(["pending", "confirmed", "preparing", "ready"])
    ).scalar() or 0
    total_revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.restaurant_id == r.id, Order.payment_status == "paid"
    ).scalar() or 0

    return {
        "restaurant_id": r.id,
        "restaurant_name": r.name,
        "staff_count": staff_count,
        "total_orders": total_orders,
        "open_orders": open_orders,
        "total_revenue": float(total_revenue),
        "subscription_plan": r.subscription_plan,
        "subscription_status": r.subscription_status,
        "is_active": r.is_active,
    }


# ── Subscription management (super admin only) ────────────────────────────────

@router.post("/{restaurant_id}/subscription", response_model=SubscriptionResponse)
def update_subscription(
    restaurant_id: int,
    body: SubscriptionUpdateRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Update denormalized fields on restaurant
    r.subscription_plan = body.plan
    r.subscription_status = body.status

    # Record subscription history
    sub = Subscription(
        restaurant_id=restaurant_id,
        plan=body.plan,
        status=body.status,
        expires_at=body.expires_at,
        created_by=current_user.id,
        notes=body.notes,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    from app.utils.helpers import log_activity
    log_activity(db, action="subscription.updated", user_id=current_user.id,
                 restaurant_id=restaurant_id, resource_type="subscription", resource_id=sub.id,
                 metadata={"plan": body.plan, "status": body.status})

    return SubscriptionResponse.model_validate(sub)


@router.get("/{restaurant_id}/subscription/history", response_model=list[SubscriptionResponse])
def get_subscription_history(
    restaurant_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    subs = (
        db.query(Subscription)
        .filter(Subscription.restaurant_id == restaurant_id)
        .order_by(Subscription.created_at.desc())
        .limit(20)
        .all()
    )
    return [SubscriptionResponse.model_validate(s) for s in subs]


# ── Restaurant staff management (super admin can manage any restaurant's staff) ──

@router.get("/{restaurant_id}/staff")
def list_restaurant_staff(
    restaurant_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.schemas.user import UserResponse
    users = db.query(User).filter(
        User.restaurant_id == restaurant_id
    ).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]
