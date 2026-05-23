from __future__ import annotations

import asyncio
import logging

import socketio

from app.auth.jwt import decode_access_token
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Restrict CORS to configured origins instead of wildcard
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list,
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid: str, environ: dict, auth: dict):
    token = (auth or {}).get("token", "")
    try:
        payload = decode_access_token(token)
        restaurant_id = payload.get("restaurant_id")
        user_id = payload.get("sub")
        if restaurant_id:
            await sio.enter_room(sid, f"restaurant_{restaurant_id}")
        await sio.save_session(sid, {"user_id": user_id, "restaurant_id": restaurant_id})
        logger.debug("Socket connected: sid=%s user=%s restaurant=%s", sid, user_id, restaurant_id)
    except Exception:
        # Unauthenticated — allow for public order tracking
        await sio.save_session(sid, {"user_id": None, "restaurant_id": None})


@sio.event
async def disconnect(sid: str):
    logger.debug("Socket disconnected: sid=%s", sid)


@sio.event
async def join_order(sid: str, data: dict):
    """Customer joins an order-specific room for real-time tracking."""
    order_id = data.get("order_id")
    if order_id:
        await sio.enter_room(sid, f"order_{order_id}")


# ── Emit helpers ──────────────────────────────────────────────────────────────
# Routes are sync def; emit helpers bridge to the async Socket.IO server
# using asyncio.create_task() so we don't block the request thread.

def _schedule(coro):
    """Schedule a Socket.IO emit coroutine on the running event loop.

    Sync routes call this bridge; uvicorn always has a running loop so
    create_task() is the normal path. The fallback handles test contexts.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running loop — best-effort fire-and-forget in test environments
        try:
            asyncio.run(coro)
        except Exception as exc:
            logger.warning("Socket emit failed (no event loop): %s", exc)


def emit_new_order(restaurant_id: int, order_id: int, order_number: str):
    _schedule(sio.emit(
        "order.created",
        {"order_id": order_id, "order_number": order_number},
        room=f"restaurant_{restaurant_id}",
    ))


def emit_order_status_changed(restaurant_id: int, order_id: int, new_status: str):
    payload = {"order_id": order_id, "status": new_status}
    _schedule(sio.emit("order.status_changed", payload, room=f"restaurant_{restaurant_id}"))
    _schedule(sio.emit("order.status_changed", payload, room=f"order_{order_id}"))
