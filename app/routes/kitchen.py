from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_admin, require_kitchen_or_admin
from app.database import get_db
from app.models.kitchen import KitchenStation, KitchenTicket
from app.models.order import Order
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.kitchen import (
    KitchenOrderResponse,
    KitchenOrderStatusUpdate,
    KitchenTicketResponse,
    KitchenTicketUpdate,
    StationCreate,
    StationResponse,
    StationUpdate,
)
from app.services.kitchen_service import build_kitchen_order, build_ticket_response
from app.utils.helpers import log_activity, paginate

router = APIRouter()


# ── Kitchen stations (real CRUD) ──────────────────────────────────────────────

@router.get("/stations", response_model=PaginatedResponse[StationResponse])
def list_stations(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    q = (
        db.query(KitchenStation)
        .filter(KitchenStation.restaurant_id == current_user.restaurant_id)
        .order_by(KitchenStation.display_order, KitchenStation.name)
    )
    return paginate(q, page, page_size, StationResponse.model_validate)


@router.post("/stations", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
def create_station(
    body: StationCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(KitchenStation).filter_by(
        restaurant_id=current_user.restaurant_id, name=body.name
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station name already exists")

    station = KitchenStation(restaurant_id=current_user.restaurant_id, **body.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    log_activity(db, action="station.created", user_id=current_user.id,
                 restaurant_id=current_user.restaurant_id, resource_type="station", resource_id=station.id)
    return StationResponse.model_validate(station)


@router.patch("/stations/{station_id}", response_model=StationResponse)
def update_station(
    station_id: int,
    body: StationUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    station = db.get(KitchenStation, station_id)
    if not station or station.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(station, field, value)
    db.commit()
    db.refresh(station)
    return StationResponse.model_validate(station)


@router.delete("/stations/{station_id}", response_model=MessageResponse)
def delete_station(
    station_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    station = db.get(KitchenStation, station_id)
    if not station or station.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    # Unlink tickets first
    db.query(KitchenTicket).filter_by(station_id=station_id).update({"station_id": None})
    db.delete(station)
    db.commit()
    return MessageResponse(message=f"Station '{station.name}' deleted")


# ── Kitchen orders view ───────────────────────────────────────────────────────

@router.get("/orders", response_model=PaginatedResponse[KitchenOrderResponse])
def list_kitchen_orders(
    page: int = 1,
    page_size: int = 30,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.table))
        .filter(
            Order.restaurant_id == current_user.restaurant_id,
            Order.status.in_(["confirmed", "preparing", "ready"]),
            Order.deleted_at.is_(None),
        )
        .order_by(Order.created_at)
    )
    return paginate(q, page, page_size, build_kitchen_order)


@router.get("/orders/history", response_model=PaginatedResponse[KitchenOrderResponse])
def kitchen_order_history(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.table))
        .filter(
            Order.restaurant_id == current_user.restaurant_id,
            Order.status.in_(["completed", "served", "cancelled"]),
            Order.deleted_at.is_(None),
        )
        .order_by(Order.created_at.desc())
    )
    return paginate(q, page, page_size, build_kitchen_order)


@router.get("/orders/{order_id}", response_model=KitchenOrderResponse)
def get_kitchen_order(
    order_id: int,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.table))
        .filter(Order.id == order_id, Order.restaurant_id == current_user.restaurant_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return build_kitchen_order(order)


@router.patch("/orders/{order_id}/status", response_model=KitchenOrderResponse)
def update_kitchen_order_status(
    order_id: int,
    body: KitchenOrderStatusUpdate,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.table), joinedload(Order.kitchen_ticket))
        .filter(Order.id == order_id, Order.restaurant_id == current_user.restaurant_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not order.can_transition_to(body.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{order.status}' to '{body.status}'",
        )

    now = datetime.now(timezone.utc)
    order.status = body.status
    ts_map = {
        "confirmed": "confirmed_at", "preparing": "preparing_at",
        "ready": "ready_at", "served": "served_at",
        "completed": "completed_at", "cancelled": "cancelled_at",
    }
    if ts_field := ts_map.get(body.status):
        setattr(order, ts_field, now)

    if order.kitchen_ticket:
        kt_map = {"preparing": "in_progress", "ready": "ready", "completed": "delivered", "cancelled": "cancelled"}
        if new_kt := kt_map.get(body.status):
            order.kitchen_ticket.status = new_kt
            if new_kt == "in_progress" and not order.kitchen_ticket.started_at:
                order.kitchen_ticket.started_at = now
            elif new_kt in ("delivered", "cancelled"):
                order.kitchen_ticket.completed_at = now

    # Free table on terminal status
    if body.status in ("completed", "cancelled", "served") and order.table_id:
        from app.models.order import RestaurantTable
        table = db.get(RestaurantTable, order.table_id)
        if table:
            table.status = "available"
            table.last_freed_at = now

    db.commit()
    db.refresh(order)

    from app.sockets.manager import emit_order_status_changed
    emit_order_status_changed(order.restaurant_id, order.id, body.status)
    log_activity(db, action=f"order.status.{body.status}", user_id=current_user.id,
                 restaurant_id=order.restaurant_id, resource_type="order", resource_id=order.id)

    return build_kitchen_order(order)


# ── Kitchen tickets ───────────────────────────────────────────────────────────

@router.get("/tickets", response_model=PaginatedResponse[KitchenTicketResponse])
def list_tickets(
    page: int = 1,
    page_size: int = 30,
    station_id: Optional[int] = None,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    q = (
        db.query(KitchenTicket)
        .options(
            joinedload(KitchenTicket.order).options(joinedload(Order.items), joinedload(Order.table)),
            joinedload(KitchenTicket.station),
            joinedload(KitchenTicket.assignee),
        )
        .filter(
            KitchenTicket.restaurant_id == current_user.restaurant_id,
            KitchenTicket.status.in_(["pending", "in_progress", "ready"]),
        )
    )
    if station_id:
        q = q.filter(KitchenTicket.station_id == station_id)
    q = q.order_by(KitchenTicket.created_at)
    return paginate(q, page, page_size, build_ticket_response)


@router.patch("/tickets/{ticket_id}", response_model=KitchenTicketResponse)
def update_ticket(
    ticket_id: int,
    body: KitchenTicketUpdate,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    ticket = (
        db.query(KitchenTicket)
        .options(
            joinedload(KitchenTicket.order).options(joinedload(Order.items), joinedload(Order.table)),
            joinedload(KitchenTicket.station),
            joinedload(KitchenTicket.assignee),
        )
        .filter(
            KitchenTicket.id == ticket_id,
            KitchenTicket.restaurant_id == current_user.restaurant_id,
        )
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    now = datetime.now(timezone.utc)
    if body.status and body.status != ticket.status:
        ticket.status = body.status
        if body.status == "in_progress" and not ticket.started_at:
            ticket.started_at = now
        elif body.status in ("delivered", "cancelled"):
            ticket.completed_at = now
    if body.priority is not None:
        ticket.priority = body.priority
    if body.notes is not None:
        ticket.notes = body.notes
    if body.assigned_to is not None:
        ticket.assigned_to = body.assigned_to
    if body.station_id is not None:
        # Validate station belongs to same restaurant
        if body.station_id == 0:
            ticket.station_id = None  # 0 = unassign
        else:
            st = db.get(KitchenStation, body.station_id)
            if not st or st.restaurant_id != current_user.restaurant_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station not found")
            ticket.station_id = body.station_id

    db.commit()
    db.refresh(ticket)
    return build_ticket_response(ticket)
