import asyncio
import logging
import socketio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import os

from app.config import get_settings
from app.routes import auth, users, restaurants, menu, orders, kitchen, analytics
from app.sockets.manager import sio

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Rate limiter (shared across routes) ───────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Startup / shutdown lifecycle ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: schedule periodic refresh-token cleanup
    asyncio.create_task(_cleanup_refresh_tokens_loop())
    logger.info("Startup complete — background tasks started")
    yield
    logger.info("Shutdown")


async def _cleanup_refresh_tokens_loop():
    """Delete revoked + expired refresh tokens older than 30 days every 6 hours."""
    while True:
        try:
            await asyncio.sleep(6 * 3600)
            _run_token_cleanup()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Token cleanup error: %s", exc)


def _run_token_cleanup():
    from app.database import SessionLocal
    from app.models.user import RefreshToken
    from app.models.password_reset import PasswordResetToken

    cutoff_refresh = datetime.now(timezone.utc) - timedelta(days=30)
    cutoff_reset = datetime.now(timezone.utc) - timedelta(hours=24)

    db = SessionLocal()
    try:
        # Stale refresh tokens
        deleted_refresh = (
            db.query(RefreshToken)
            .filter(
                (RefreshToken.is_revoked == True) | (RefreshToken.expires_at < cutoff_refresh)
            )
            .delete(synchronize_session=False)
        )
        # Expired/used password reset tokens
        deleted_reset = (
            db.query(PasswordResetToken)
            .filter(
                (PasswordResetToken.used_at.is_not(None)) |
                (PasswordResetToken.expires_at < cutoff_reset)
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted_refresh or deleted_reset:
            logger.info(
                "Token cleanup: %d refresh, %d password-reset tokens removed",
                deleted_refresh, deleted_reset,
            )
    finally:
        db.close()


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Admizo Restaurant OS API",
    version="1.0.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Centralized error handlers — always return JSON ────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic validation errors → clean 422 JSON."""
    errors: dict = {}
    for error in exc.errors():
        loc = ".".join(str(x) for x in error["loc"] if x != "body")
        errors[loc or "body"] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: prevents HTML 500 pages leaking to the frontend."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(auth.router,        prefix=f"{PREFIX}/auth",        tags=["auth"])
app.include_router(users.router,       prefix=f"{PREFIX}/users",       tags=["users"])
app.include_router(restaurants.router, prefix=f"{PREFIX}/restaurants", tags=["restaurants"])
app.include_router(menu.router,        prefix=f"{PREFIX}/menu",        tags=["menu"])
app.include_router(orders.router,      prefix=f"{PREFIX}/orders",      tags=["orders"])
app.include_router(kitchen.router,     prefix=f"{PREFIX}/kitchen",     tags=["kitchen"])
app.include_router(analytics.router,   prefix=f"{PREFIX}/analytics",   tags=["analytics"])

# ── Static media ──────────────────────────────────────────────────────────────
os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": app.version}


# ── Socket.IO ASGI wrapper ────────────────────────────────────────────────────
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)
