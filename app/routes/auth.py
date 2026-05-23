from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.config import get_settings
from app.database import get_db
from app.models.user import RefreshToken, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserInToken,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    authenticate_user,
    complete_password_reset,
    create_user_and_restaurant,
    initiate_password_reset,
)
from app.utils.helpers import get_client_ip, log_activity

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

_ACCESS_MAX_AGE = 60 * 15            # 15 minutes
_REFRESH_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    """Set httpOnly cookies. `secure=True` in production (HTTPS required)."""
    _secure = get_settings().cookie_secure
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=_secure,
        samesite="lax",
        max_age=_ACCESS_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=_secure,
        samesite="lax",
        max_age=_REFRESH_MAX_AGE,
        path="/api/v1/auth",
    )


def _issue_tokens(user: User, db: Session, request: Request, response: Response) -> TokenResponse:
    raw_refresh = generate_refresh_token()
    token_hash = hash_refresh_token(raw_refresh)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=refresh_token_expiry(),
        device_info=request.headers.get("user-agent", "")[:255],
        ip_address=get_client_ip(request),
    )
    db.add(rt)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    access = create_access_token(user.id, user.role, user.restaurant_id)
    _set_auth_cookies(response, access, raw_refresh)

    return TokenResponse(
        access=access,
        refresh=raw_refresh,
        user=UserInToken.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, response: Response, body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    result = _issue_tokens(user, db, request, response)
    log_activity(db, action="user.login", user_id=user.id,
                 restaurant_id=user.restaurant_id, ip=get_client_ip(request))
    return result


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, response: Response, body: RegisterRequest, db: Session = Depends(get_db)):
    user = create_user_and_restaurant(db, body)
    result = _issue_tokens(user, db, request, response)
    log_activity(db, action="user.register", user_id=user.id,
                 restaurant_id=user.restaurant_id, ip=get_client_ip(request))
    return result


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh_token(
    request: Request,
    response: Response,
    cookie_refresh: Optional[str] = Cookie(default=None, alias="refresh_token"),
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
):
    raw_refresh = cookie_refresh or (body.refresh if body else None)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided")

    token_hash = hash_refresh_token(raw_refresh)
    rt = db.query(RefreshToken).filter_by(token_hash=token_hash).first()

    if not rt or rt.is_revoked or rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    rt.is_revoked = True
    db.flush()

    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return _issue_tokens(user, db, request, response)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    cookie_refresh: Optional[str] = Cookie(default=None, alias="refresh_token"),
    body: Optional[LogoutRequest] = None,
    db: Session = Depends(get_db),
):
    raw_refresh = cookie_refresh or (body.refresh if body else None)
    if raw_refresh:
        token_hash = hash_refresh_token(raw_refresh)
        rt = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
        if rt:
            rt.is_revoked = True
            db.commit()

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return MessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    initiate_password_reset(db, body.email)
    return MessageResponse(message="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    ok = complete_password_reset(db, body.token, body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return MessageResponse(message="Password reset successfully. Please log in again.")
