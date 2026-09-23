from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin, require_restaurant_admin, require_super_admin
from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import (
    AdminResetPasswordRequest, ChangePasswordRequest,
    UserCreate, UserResponse, UserUpdate,
)
from app.services.auth_service import hash_password, verify_password
from app.utils.helpers import paginate

router = APIRouter()


def _serialize(user: User) -> UserResponse:
    data = UserResponse.model_validate(user)
    if user.restaurant:
        data.restaurant_name = user.restaurant.name
    return data


# ── Own profile ───────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _serialize(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(body: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = {"full_name", "phone"}  # users can only update their own name/phone via /me
    for field in allowed:
        value = getattr(body, field, None)
        if value is not None:
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _serialize(current_user)


@router.post("/me/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully")


# ── Restaurant admin — manage own restaurant staff ────────────────────────────

@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users(
    page: int = 1,
    page_size: int = 20,
    restaurant_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.deleted_at.is_(None))
    if current_user.role == "super_admin":
        # Super admin can filter by restaurant or see all
        if restaurant_id is not None:
            q = q.filter(User.restaurant_id == restaurant_id)
        else:
            q = q.filter(User.role != "super_admin")  # exclude other super admins for clarity
    else:
        # Restaurant staff see only their own restaurant
        q = q.filter(User.restaurant_id == current_user.restaurant_id)
    q = q.order_by(User.created_at.desc())
    return paginate(q, page, page_size, _serialize)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Determine which restaurant to assign to
    target_restaurant_id = body.restaurant_id if current_user.role == "super_admin" else current_user.restaurant_id
    if not target_restaurant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No restaurant context")
    if not db.get(Restaurant, target_restaurant_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Restaurant not found")

    user = User(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=body.role,
        restaurant_id=target_restaurant_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Super admin can update any user; restaurant admin only their own staff
    if current_user.role != "super_admin" and user.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.delete("/{user_id}", response_model=MessageResponse)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.role != "super_admin" and user.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user.is_active = False
    db.commit()
    return MessageResponse(message="User deactivated")


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
def admin_reset_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.role != "super_admin" and user.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Password reset successfully")
