from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_admin, require_roles
from app.database import get_db
from app.models.order import Order, OrderItem, OrderStatusHistory, RestaurantTable, TableQRCode
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.order import (
    OrderCreate, OrderListItem, OrderPaymentUpdate, OrderResponse,
    OrderStatusUpdate, PublicOrderCreate, PublicOrderTrackResponse,
    TableCreate, TableQRCodeResponse, TableResponse, TableUpdate,
)
from app.services.order_service import build_order_list_item, build_order_response, create_order
from app.utils.helpers import paginate

router = APIRouter()


def _table_response(t: RestaurantTable) -> TableResponse:
    data = TableResponse.model_validate(t)
    try:
        active_qr = t.active_qr
        data.qr_token = active_qr.qr_token if active_qr else t.qr_token
        data.qr_url = active_qr.qr_url if active_qr and active_qr.qr_url else t.qr_url
    except Exception:
        pass
    return data


def _build_qr_url(table: RestaurantTable, qr_token: str) -> str:
    from app.config import get_settings
    return f"{get_settings().frontend_url}/order/{table.restaurant.slug}/{qr_token}"


def _create_table_qr(db: Session, table: RestaurantTable, user: User) -> TableQRCode:
    db.query(TableQRCode).filter(
        TableQRCode.table_id == table.id,
        TableQRCode.status == "active",
        TableQRCode.deleted_at.is_(None),
    ).update({"status": "rotated", "rotated_at": datetime.now(timezone.utc)}, synchronize_session=False)
    qr_token = secrets.token_urlsafe(32)
    qr = TableQRCode(
        restaurant_id=table.restaurant_id,
        table_id=table.id,
        qr_id=f"qr_{secrets.token_urlsafe(16)}",
        qr_token=qr_token,
        qr_url=_build_qr_url(table, qr_token),
        created_by=user.id,
        created_by_role=user.role,
    )
    table.qr_token = qr_token
    db.add(qr)
    return qr


@router.get("/tables", response_model=PaginatedResponse[TableResponse])
def list_tables(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(RestaurantTable).filter(
        RestaurantTable.restaurant_id == current_user.restaurant_id
    ).order_by(RestaurantTable.table_number)
    return paginate(q, page, page_size, _table_response)


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
def create_table(
    body: TableCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(RestaurantTable).filter_by(
        restaurant_id=current_user.restaurant_id, table_number=body.table_number
    ).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table number already exists")
    table = RestaurantTable(
        restaurant_id=current_user.restaurant_id,
        qr_token=secrets.token_urlsafe(32),
        **body.model_dump(),
    )
    db.add(table)
    db.flush()
    _create_table_qr(db, table, current_user)
    db.commit()
    db.refresh(table)
    return _table_response(table)


@router.patch("/tables/{table_id}", response_model=TableResponse)
def update_table(
    table_id: int,
    body: TableUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(table, field, value)
    db.commit()
    db.refresh(table)
    return _table_response(table)


@router.delete("/tables/{table_id}", response_model=MessageResponse)
def deactivate_table(
    table_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    table.is_active = False
    db.commit()
    return MessageResponse(message="Table deactivated")


@router.post("/tables/{table_id}/rotate-qr", response_model=TableResponse)
def rotate_qr(
    table_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    _create_table_qr(db, table, current_user)
    db.commit()
    db.refresh(table)
    return _table_response(table)


@router.get("/tables/{table_id}/qr-codes", response_model=list[TableQRCodeResponse])
def list_table_qr_codes(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    if current_user.role != "super_admin" and table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return db.query(TableQRCode).filter(
        TableQRCode.table_id == table_id,
        TableQRCode.deleted_at.is_(None),
    ).order_by(TableQRCode.created_at.desc()).all()


@router.post("/tables/{table_id}/qr-codes", response_model=TableQRCodeResponse, status_code=status.HTTP_201_CREATED)
def create_table_qr_code(
    table_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    if current_user.role != "super_admin" and table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    qr = _create_table_qr(db, table, current_user)
    db.commit()
    db.refresh(qr)
    return qr


@router.patch("/qr-codes/{qr_id}/rotate", response_model=TableQRCodeResponse)
def rotate_qr_code(
    qr_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    qr = db.query(TableQRCode).filter_by(qr_id=qr_id, deleted_at=None).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found")
    if current_user.role != "super_admin" and qr.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    table = db.get(RestaurantTable, qr.table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    new_qr = _create_table_qr(db, table, current_user)
    db.commit()
    db.refresh(new_qr)
    return new_qr


@router.patch("/qr-codes/{qr_id}/disable", response_model=TableQRCodeResponse)
def disable_qr_code(
    qr_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    qr = db.query(TableQRCode).filter_by(qr_id=qr_id, deleted_at=None).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found")
    if current_user.role != "super_admin" and qr.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    qr.status = "disabled"
    db.commit()
    db.refresh(qr)
    return qr


@router.get("", response_model=PaginatedResponse[OrderListItem])
def list_orders(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    payment_status: Optional[str] = None,
    restaurant_id: Optional[int] = None,  # super_admin only filter
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.table))
    )

    # Tenant scoping: super_admin can filter by restaurant_id or see all
    if current_user.role == "super_admin":
        if restaurant_id:
            q = q.filter(Order.restaurant_id == restaurant_id)
        # else: no filter — super_admin sees all orders
    else:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)

    # Exclude soft-deleted
    q = q.filter(Order.deleted_at.is_(None))

    if status:
        q = q.filter(Order.status == status)
    if payment_status:
        q = q.filter(Order.payment_status == payment_status)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            Order.order_number.ilike(term) |
            Order.customer_name.ilike(term) |
            Order.customer_phone.ilike(term)
        )
    q = q.order_by(Order.created_at.desc())
    return paginate(q, page, page_size, lambda o: build_order_list_item(o, db))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_new_order(
    body: OrderCreate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    return create_order(db, body, current_user.restaurant_id, current_user.id)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Order).options(
        joinedload(Order.items), joinedload(Order.table), joinedload(Order.kitchen_ticket)
    ).filter(Order.id == order_id, Order.deleted_at.is_(None))
    # Super admin can access any restaurant's order
    if current_user.role != "super_admin":
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return build_order_response(order, db)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order or order.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not order.can_transition_to(body.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{order.status}' to '{body.status}'",
        )

    now = datetime.now(timezone.utc)
    previous_status = order.status
    order.status = body.status
    timestamp_map = {
        "confirmed": "confirmed_at", "preparing": "preparing_at",
        "ready": "ready_at", "served": "served_at",
        "completed": "completed_at", "cancelled": "cancelled_at",
    }
    if ts_field := timestamp_map.get(body.status):
        setattr(order, ts_field, now)

    if order.kitchen_ticket:
        kt_map = {"preparing": "in_progress", "ready": "ready",
                  "completed": "delivered", "cancelled": "cancelled"}
        if new_kt := kt_map.get(body.status):
            previous_kt_status = order.kitchen_ticket.status
            order.kitchen_ticket.status = new_kt
            if new_kt == "in_progress" and not order.kitchen_ticket.started_at:
                order.kitchen_ticket.started_at = now
            elif new_kt in ("delivered", "cancelled"):
                order.kitchen_ticket.completed_at = now
            from app.models.kitchen import KitchenTicketStatusHistory
            db.add(KitchenTicketStatusHistory(
                restaurant_id=order.restaurant_id,
                ticket_id=order.kitchen_ticket.id,
                from_status=previous_kt_status,
                to_status=new_kt,
                changed_by=current_user.id,
            ))

    # Free the table when the order reaches a terminal status
    if body.status in ("completed", "cancelled", "served") and order.table_id:
        table = db.get(RestaurantTable, order.table_id)
        if table:
            table.status = "available"
            table.last_freed_at = now

    db.add(OrderStatusHistory(
        restaurant_id=order.restaurant_id,
        order_id=order.id,
        from_status=previous_status,
        to_status=body.status,
        changed_by=current_user.id,
        source="staff",
    ))
    db.commit()
    db.refresh(order)

    from app.sockets.manager import emit_order_status_changed
    emit_order_status_changed(order.restaurant_id, order.id, body.status)

    from app.utils.helpers import log_activity
    log_activity(db, action=f"order.status.{body.status}", user_id=current_user.id,
                 restaurant_id=order.restaurant_id, resource_type="order", resource_id=order.id)

    return build_order_response(order, db)


@router.patch("/{order_id}/payment", response_model=OrderResponse)
def update_payment_status(
    order_id: int,
    body: OrderPaymentUpdate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order or order.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if body.payment_status not in {"unpaid", "paid", "partially_paid", "refunded"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment status")
    order.payment_status = body.payment_status
    db.commit()
    db.refresh(order)
    return build_order_response(order, db)


@router.delete("/{order_id}", response_model=MessageResponse)
def soft_delete_order(
    order_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete a cancelled/completed order (admin only). Hides from all lists."""
    order = db.get(Order, order_id)
    if not order or order.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status not in ("cancelled", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only cancelled or completed orders can be deleted",
        )
    order.deleted_at = datetime.now(timezone.utc)
    db.commit()
    from app.utils.helpers import log_activity
    log_activity(db, action="order.deleted", user_id=current_user.id,
                 restaurant_id=order.restaurant_id, resource_type="order", resource_id=order.id)
    return MessageResponse(message=f"Order #{order.order_number} removed from records")


@router.post("/public/{slug}/{qr_token}", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def public_create_order(
    slug: str,
    qr_token: str,
    body: PublicOrderCreate,
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter_by(slug=slug, is_active=True).first()
    if not restaurant or not restaurant.allow_online_ordering:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found or ordering disabled")

    qr = db.query(TableQRCode).filter_by(
        restaurant_id=restaurant.id,
        qr_token=qr_token,
        status="active",
        deleted_at=None,
    ).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")
    qr.scan_count += 1
    qr.last_scanned_at = datetime.now(timezone.utc)
    table = db.get(RestaurantTable, qr.table_id)
    if not table or not table.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")

    order_data = OrderCreate(
        table_id=table.id,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        special_instructions=body.special_instructions,
        order_type="dine_in",
        items=body.items,
    )
    return create_order(db, order_data, restaurant.id, created_by=None)


@router.get("/public/track/{order_id}", response_model=PublicOrderTrackResponse)
def public_track_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return PublicOrderTrackResponse.model_validate(order)
