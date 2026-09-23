from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.billing import Bill, BillItem, Payment
from app.models.order import Order
from app.models.user import User
from app.schemas.billing import BillCreate, BillItemResponse, BillResponse, PaymentCreate
from app.schemas.common import PaginatedResponse
from app.utils.helpers import paginate

router = APIRouter()


def _serialize_bill(bill: Bill) -> BillResponse:
    data = BillResponse.model_validate(bill)
    data.subtotal = float(bill.subtotal)
    data.tax_amount = float(bill.tax_amount)
    data.discount_amount = float(bill.discount_amount)
    data.service_charge = float(bill.service_charge)
    data.total_amount = float(bill.total_amount)
    data.paid_amount = float(bill.paid_amount)
    data.items = [BillItemResponse.model_validate(i) for i in bill.items]
    for item in data.items:
        item.unit_price = float(item.unit_price)
        item.total_price = float(item.total_price)
    return data


def _next_bill_number(db: Session, restaurant_id: int) -> str:
    count = db.query(func.count(Bill.id)).filter(Bill.restaurant_id == restaurant_id).scalar() or 0
    return f"BILL-{count + 1:06d}"


@router.get("", response_model=PaginatedResponse[BillResponse])
def list_bills(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    q = db.query(Bill).options(joinedload(Bill.items)).filter(
        Bill.restaurant_id == current_user.restaurant_id,
        Bill.deleted_at.is_(None),
    ).order_by(Bill.created_at.desc())
    return paginate(q, page, page_size, _serialize_bill)


@router.post("", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
def create_bill(
    body: BillCreate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    order = db.query(Order).options(joinedload(Order.items)).filter(
        Order.id == body.order_id,
        Order.restaurant_id == current_user.restaurant_id,
        Order.deleted_at.is_(None),
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    existing = db.query(Bill).options(joinedload(Bill.items)).filter(
        Bill.order_id == order.id,
        Bill.deleted_at.is_(None),
    ).first()
    if existing:
        return _serialize_bill(existing)

    bill = Bill(
        restaurant_id=order.restaurant_id,
        order_id=order.id,
        bill_number=_next_bill_number(db, order.restaurant_id),
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        discount_amount=order.discount_amount,
        service_charge=order.service_charge,
        total_amount=order.total_amount,
        created_by=current_user.id,
    )
    db.add(bill)
    db.flush()
    for item in order.items:
        db.add(BillItem(
            bill_id=bill.id,
            order_item_id=item.id,
            name=item.menu_item_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
        ))
    db.commit()
    db.refresh(bill)
    return _serialize_bill(bill)


@router.get("/{bill_id}", response_model=BillResponse)
def get_bill(
    bill_id: int,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).options(joinedload(Bill.items)).filter(
        Bill.id == bill_id,
        Bill.restaurant_id == current_user.restaurant_id,
        Bill.deleted_at.is_(None),
    ).first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return _serialize_bill(bill)


@router.post("/{bill_id}/payments", response_model=BillResponse)
def add_payment(
    bill_id: int,
    body: PaymentCreate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).options(joinedload(Bill.items)).filter(
        Bill.id == bill_id,
        Bill.restaurant_id == current_user.restaurant_id,
        Bill.deleted_at.is_(None),
    ).first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    db.add(Payment(
        restaurant_id=bill.restaurant_id,
        bill_id=bill.id,
        payment_method_id=body.payment_method_id,
        amount=body.amount,
        reference=body.reference,
        notes=body.notes,
        created_by=current_user.id,
    ))
    bill.paid_amount = Decimal(str(bill.paid_amount)) + Decimal(str(body.amount))
    if bill.paid_amount >= bill.total_amount:
        bill.status = "paid"
        bill.closed_at = datetime.now(timezone.utc)
        order = db.get(Order, bill.order_id)
        if order:
            order.payment_status = "paid"
    else:
        bill.status = "partial"
    db.commit()
    db.refresh(bill)
    return _serialize_bill(bill)
