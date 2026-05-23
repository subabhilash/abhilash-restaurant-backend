from __future__ import annotations

from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.utils.helpers import generate_slug

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter_by(email=email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_user_and_restaurant(db: Session, data: RegisterRequest) -> User:
    from fastapi import HTTPException, status as http_status

    email = data.email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    slug = generate_slug(data.restaurant_name, db)
    restaurant = Restaurant(
        name=data.restaurant_name,
        slug=slug,
        subscription_plan="free",
        subscription_status="trial",
    )
    db.add(restaurant)
    db.flush()

    user = User(
        email=email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role="admin",
        restaurant_id=restaurant.id,
    )
    db.add(user)
    db.flush()

    restaurant.owner_id = user.id
    db.commit()
    db.refresh(user)
    return user


def initiate_password_reset(db: Session, email: str) -> None:
    """Generate a 1-hour HMAC token, store its hash, and email the reset link."""
    import hashlib, hmac, secrets
    from datetime import datetime, timedelta, timezone
    from app.models.password_reset import PasswordResetToken
    from app.config import get_settings

    user = db.query(User).filter_by(email=email.lower().strip(), is_active=True).first()
    if not user:
        return  # Silently ignore — prevents email enumeration

    settings = get_settings()

    # Generate URL-safe token and store its hash
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    # Revoke any existing unused tokens for this user
    db.query(PasswordResetToken).filter_by(user_id=user.id, used_at=None).delete()

    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    ))
    db.commit()

    # Send email via Resend
    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
    _send_reset_email(user.email, user.full_name, reset_url, settings)


def _send_reset_email(to_email: str, full_name: str, reset_url: str, settings) -> None:
    """Send password reset email via Resend API."""
    if not settings.resend_api_key:
        return  # No email provider configured — skip silently in dev

    try:
        import httpx
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Reset your Admizo password",
                "html": f"""
                <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
                  <h2>Password Reset</h2>
                  <p>Hi {full_name},</p>
                  <p>Click the button below to reset your password. This link expires in <strong>1 hour</strong>.</p>
                  <a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;margin:16px 0">
                    Reset Password
                  </a>
                  <p style="color:#6b7280;font-size:14px">If you didn't request this, you can safely ignore this email.</p>
                  <p style="color:#6b7280;font-size:12px">Link: {reset_url}</p>
                </div>
                """,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        pass  # Don't expose email failures to caller


def complete_password_reset(db: Session, token: str, new_password: str) -> bool:
    """Validate the HMAC token, update password, mark token used."""
    import hashlib
    from datetime import datetime, timezone
    from app.models.password_reset import PasswordResetToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    prt = db.query(PasswordResetToken).filter_by(token_hash=token_hash, used_at=None).first()
    if not prt:
        return False
    if prt.expires_at.replace(tzinfo=timezone.utc) < now:
        return False

    user = db.get(User, prt.user_id)
    if not user or not user.is_active:
        return False

    user.password_hash = hash_password(new_password)
    prt.used_at = now
    # Revoke all refresh tokens for this user (force re-login everywhere)
    from app.models.user import RefreshToken
    db.query(RefreshToken).filter_by(user_id=user.id, is_revoked=False).update({"is_revoked": True})
    db.commit()
    return True
