from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


# ── Role guards ───────────────────────────────────────────────────────────────

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_restaurant_admin(current_user: User = Depends(get_current_user)) -> User:
    """Only restaurant-level admins (not super_admin) who own a restaurant."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant admin access required")
    return current_user


def require_kitchen_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "admin", "kitchen"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kitchen or admin access required")
    return current_user


def require_roles(*roles: str):
    """Return a dependency that enforces one of the given roles."""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return current_user
    return _check


def assert_restaurant_access(user: User, restaurant_id: int) -> None:
    """Raise 403 if a non-super_admin user doesn't belong to the restaurant."""
    if user.role == "super_admin":
        return
    if user.restaurant_id != restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this restaurant")


def require_active_subscription(current_user: User = Depends(get_current_user)) -> User:
    """Block admin actions if the restaurant subscription is not active/trial."""
    if current_user.role == "super_admin":
        return current_user
    if not current_user.restaurant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No restaurant assigned")
    if current_user.restaurant.subscription_status not in ("trial", "active"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Subscription is {current_user.restaurant.subscription_status}. Please renew to continue.",
        )
    return current_user
