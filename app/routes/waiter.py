from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.order import RestaurantTable, TableQRCode
from app.models.restaurant import Restaurant
from app.models.user import User
from app.models.waiter import WaiterCall, WaiterCallStatusHistory
from app.schemas.common import PaginatedResponse
from app.schemas.waiter import PublicWaiterCallCreate, WaiterCallCreate, WaiterCallResponse, WaiterCallUpdate
from app.utils.helpers import paginate

router = APIRouter()


def _record_history(db: Session, call: WaiterCall, from_status: Optional[str], changed_by: Optional[int]) -> None:
    db.add(WaiterCallStatusHistory(
        waiter_call_id=call.id,
        from_status=from_status,
        to_status=call.status,
        changed_by=changed_by,
    ))


@router.get("/calls", response_model=PaginatedResponse[WaiterCallResponse])
def list_calls(
    page: int = 1,
    page_size: int = 50,
    call_status: Optional[str] = None,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    q = db.query(WaiterCall).filter(WaiterCall.restaurant_id == current_user.restaurant_id)
    if call_status:
        q = q.filter(WaiterCall.status == call_status)
    q = q.order_by(WaiterCall.created_at.desc())
    return paginate(q, page, page_size, WaiterCallResponse.model_validate)


@router.post("/calls", response_model=WaiterCallResponse, status_code=status.HTTP_201_CREATED)
def create_call(
    body: WaiterCallCreate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    table = db.get(RestaurantTable, body.table_id)
    if not table or table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    call = WaiterCall(
        restaurant_id=current_user.restaurant_id,
        table_id=table.id,
        reason=body.reason,
        notes=body.notes,
    )
    db.add(call)
    db.flush()
    _record_history(db, call, None, current_user.id)
    db.commit()
    db.refresh(call)
    return call


@router.patch("/calls/{call_id}", response_model=WaiterCallResponse)
def update_call(
    call_id: int,
    body: WaiterCallUpdate,
    current_user: User = Depends(require_roles("admin", "waiter")),
    db: Session = Depends(get_db),
):
    call = db.get(WaiterCall, call_id)
    if not call or call.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waiter call not found")
    previous = call.status
    if body.status and body.status != call.status:
        call.status = body.status
        now = datetime.now(timezone.utc)
        if body.status == "acknowledged":
            call.acknowledged_at = now
        if body.status in ("resolved", "cancelled"):
            call.resolved_at = now
        _record_history(db, call, previous, current_user.id)
    if body.assigned_to is not None:
        call.assigned_to = body.assigned_to
    if body.notes is not None:
        call.notes = body.notes
    db.commit()
    db.refresh(call)
    return call


@router.post("/public/{slug}/calls", response_model=WaiterCallResponse, status_code=status.HTTP_201_CREATED)
def public_create_call(
    slug: str,
    body: PublicWaiterCallCreate,
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter_by(slug=slug, is_active=True).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    qr = db.query(TableQRCode).filter_by(
        restaurant_id=restaurant.id,
        qr_token=body.qr_token,
        status="active",
        deleted_at=None,
    ).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")
    table = db.get(RestaurantTable, qr.table_id)
    if not table or not table.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")
    call = WaiterCall(
        restaurant_id=restaurant.id,
        table_id=table.id,
        reason=body.reason,
        notes=body.notes,
    )
    db.add(call)
    db.flush()
    _record_history(db, call, None, None)
    db.commit()
    db.refresh(call)
    return call
