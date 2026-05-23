from __future__ import annotations

from datetime import datetime, timezone

from app.models.kitchen import KitchenTicket
from app.models.order import Order
from app.schemas.kitchen import (
    KitchenOrderItemResponse,
    KitchenOrderResponse,
    KitchenTicketResponse,
)


def build_kitchen_order(order: Order) -> KitchenOrderResponse:
    now = datetime.now(timezone.utc)
    ref = order.confirmed_at or order.created_at
    if ref:
        ref_aware = ref if ref.tzinfo else ref.replace(tzinfo=timezone.utc)
        elapsed = int((now - ref_aware).total_seconds())
    else:
        elapsed = 0

    items = [
        KitchenOrderItemResponse(
            id=item.id,
            menu_item_name=item.menu_item_name,
            quantity=item.quantity,
            special_instructions=item.special_instructions,
        )
        for item in order.items
    ]

    return KitchenOrderResponse(
        id=order.id,
        order_number=order.order_number,
        table_number=order.table.table_number if order.table else None,
        order_type=order.order_type,
        status=order.status,
        special_instructions=order.special_instructions,
        items=items,
        confirmed_at=order.confirmed_at,
        preparing_at=order.preparing_at,
        ready_at=order.ready_at,
        created_at=order.created_at,
        elapsed_seconds=elapsed,
    )


def build_ticket_response(ticket: KitchenTicket) -> KitchenTicketResponse:
    items = []
    order_number = ""
    table_number = None

    if ticket.order:
        order_number = ticket.order.order_number
        table_number = ticket.order.table.table_number if ticket.order.table else None
        items = [
            KitchenOrderItemResponse(
                id=item.id,
                menu_item_name=item.menu_item_name,
                quantity=item.quantity,
                special_instructions=item.special_instructions,
            )
            for item in ticket.order.items
        ]

    return KitchenTicketResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        order_number=order_number,
        table_number=table_number,
        station_id=ticket.station_id,
        station_name=ticket.station.name if ticket.station else None,
        assigned_to=ticket.assigned_to,
        assigned_to_name=ticket.assignee.full_name if ticket.assignee else None,
        status=ticket.status,
        priority=ticket.priority,
        notes=ticket.notes,
        items=items,
        started_at=ticket.started_at,
        completed_at=ticket.completed_at,
        prep_time_seconds=ticket.prep_time_seconds,
        created_at=ticket.created_at,
    )
