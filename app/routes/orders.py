from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_admin, require_roles
from app.database import get_db
from app.models.order import Order, OrderItem, RestaurantTable
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.order import (
    OrderCreate, OrderListItem, OrderPaymentUpdate, OrderResponse,
    OrderStatusUpdate, PublicOrderCreate, PublicOrderTrackResponse,
    TableCreate, TableResponse, TableUpdate,
)
from app.services.order_service import build_order_list_item, build_order_response, create_order
from app.utils.helpers import paginate

router = APIRouter()


def _table_response(t: RestaurantTable) -> TableResponse:
    data = TableResponse.model_validate(t)
    try:
        data.qr_url = t.qr_url
    except Exception:
        pass
    return data


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


@router.get("/tables/{table_id}/qr-image")
def get_qr_image(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the QR code as a PNG image stream."""
    import qrcode
    from qrcode.image.pure import PyPNGImage

    table = db.get(RestaurantTable, table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(table.qr_url)
    qr.make(fit=True)

    img = qr.make_image(image_factory=PyPNGImage)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="table-{table.table_number}-qr.png"'},
    )


@router.post("/tables/{table_id}/rotate-qr", response_model=TableResponse)
def rotate_qr(
    table_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    table.qr_token = secrets.token_urlsafe(32)
    db.commit()
    db.refresh(table)
    return _table_response(table)


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
            order.kitchen_ticket.status = new_kt
            if new_kt == "in_progress" and not order.kitchen_ticket.started_at:
                order.kitchen_ticket.started_at = now
            elif new_kt in ("delivered", "cancelled"):
                order.kitchen_ticket.completed_at = now

    # Free the table when the order reaches a terminal status
    if body.status in ("completed", "cancelled", "served") and order.table_id:
        table = db.get(RestaurantTable, order.table_id)
        if table:
            table.status = "available"
            table.last_freed_at = now

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

    table = db.query(RestaurantTable).filter_by(
        restaurant_id=restaurant.id, qr_token=qr_token, is_active=True
    ).first()
    if not table:
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
