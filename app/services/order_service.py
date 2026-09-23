from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.menu import MenuItem
from app.models.order import Order, OrderItem, OrderStatusHistory, RestaurantTable
from app.models.kitchen import KitchenTicket
from app.models.restaurant import Restaurant
from app.schemas.order import OrderCreate, OrderItemResponse, OrderListItem, OrderResponse
from app.sockets.manager import emit_new_order


def _generate_order_number(db: Session, restaurant_id: int) -> str:
    """Generate a collision-safe daily order number using MAX instead of COUNT.

    Using MAX(order_number) within the day prevents the race condition where two
    concurrent requests read the same COUNT and produce duplicate numbers.
    The unique constraint on (restaurant_id, order_number) is the final safety net.
    """
    from datetime import date
    from sqlalchemy import func, text

    date_str = date.today().strftime("%Y%m%d")
    prefix = f"{date_str}-"

    # Lock the table range for this restaurant today to serialise concurrent inserts
    result = db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(order_number FROM :len) AS INTEGER)), 0) "
            "FROM orders "
            "WHERE restaurant_id = :rid AND order_number LIKE :prefix "
            "FOR UPDATE SKIP LOCKED"
        ),
        {"rid": restaurant_id, "prefix": f"{prefix}%", "len": len(prefix) + 1},
    ).scalar()

    seq = (result or 0) + 1
    return f"{prefix}{seq:04d}"


def create_order(
    db: Session,
    data: OrderCreate,
    restaurant_id: int,
    created_by: Optional[int],
) -> OrderResponse:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    if not data.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order must have at least one item")

    if data.table_id:
        table = db.get(RestaurantTable, data.table_id)
        if not table or table.restaurant_id != restaurant_id or not table.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid table")

    subtotal = Decimal("0")
    order_items_data = []
    for item_in in data.items:
        menu_item = db.get(MenuItem, item_in.menu_item_id)
        if not menu_item or menu_item.restaurant_id != restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Menu item {item_in.menu_item_id} not found",
            )
        if not menu_item.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{menu_item.name}' is currently unavailable",
            )
        unit_price = Decimal(str(menu_item.price))
        total_price = unit_price * item_in.quantity
        subtotal += total_price
        order_items_data.append({
            "menu_item_id": menu_item.id,
            "menu_item_name": menu_item.name,
            "quantity": item_in.quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "special_instructions": item_in.special_instructions,
        })

    tax_amount = subtotal * Decimal(str(restaurant.tax_rate)) / 100
    service_charge = subtotal * Decimal(str(restaurant.service_charge_rate)) / 100
    total_amount = subtotal + tax_amount + service_charge

    order = Order(
        restaurant_id=restaurant_id,
        table_id=data.table_id,
        order_number=_generate_order_number(db, restaurant_id),
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        order_type=data.order_type,
        special_instructions=data.special_instructions,
        subtotal=float(subtotal),
        tax_amount=float(tax_amount),
        service_charge=float(service_charge),
        total_amount=float(total_amount),
        created_by=created_by,
        status="confirmed" if restaurant.auto_accept_orders else "pending",
    )
    if restaurant.auto_accept_orders:
        order.confirmed_at = datetime.now(timezone.utc)

    db.add(order)
    db.flush()
    db.add(OrderStatusHistory(
        restaurant_id=restaurant_id,
        order_id=order.id,
        from_status=None,
        to_status=order.status,
        changed_by=created_by,
        source="public" if created_by is None else "staff",
    ))

    for item_data in order_items_data:
        db.add(OrderItem(order_id=order.id, **item_data))

    if restaurant.kitchen_display_enabled:
        db.add(KitchenTicket(restaurant_id=restaurant_id, order_id=order.id))

    if data.table_id:
        table = db.get(RestaurantTable, data.table_id)
        if table:
            table.occupied_since = datetime.now(timezone.utc)
            table.status = "occupied"

    db.commit()
    db.refresh(order)

    emit_new_order(restaurant_id, order.id, order.order_number)

    from app.utils.helpers import log_activity
    log_activity(db, action="order.created", user_id=created_by,
                 restaurant_id=restaurant_id, resource_type="order", resource_id=order.id,
                 metadata={"order_number": order.order_number, "total": float(total_amount)})

    return build_order_response(order, db)


def build_order_response(order: Order, db: Session) -> OrderResponse:
    """Serialize a full order with its items. Numeric fields coerced via Pydantic."""
    items = [OrderItemResponse.model_validate(item) for item in order.items]
    data = OrderResponse.model_validate(order)
    data.table_number = order.table.table_number if order.table else None
    data.items = items
    data.item_count = len(items)
    # Coerce Decimal → float explicitly (Pydantic v2 may keep Decimal for Numeric columns)
    data.subtotal = float(order.subtotal)
    data.tax_amount = float(order.tax_amount)
    data.service_charge = float(order.service_charge)
    data.discount_amount = float(order.discount_amount)
    data.total_amount = float(order.total_amount)
    return data


def build_order_list_item(order: Order, db: Session) -> OrderListItem:
    data = OrderListItem.model_validate(order)
    data.table_number = order.table.table_number if order.table else None
    data.item_count = len(order.items)
    data.total_amount = float(order.total_amount)
    return data
