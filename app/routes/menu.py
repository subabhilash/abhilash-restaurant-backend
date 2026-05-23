from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.menu import Category, MenuItem
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.menu import (
    CategoryCreate, CategoryResponse, CategoryUpdate,
    MenuItemCreate, MenuItemResponse, MenuItemUpdate,
    PublicCategoryResponse, PublicMenuItemResponse, PublicMenuResponse,
)
from app.utils.helpers import paginate

router = APIRouter()


def _serialize_category(cat: Category, db: Session) -> CategoryResponse:
    count = db.query(func.count(MenuItem.id)).filter(
        MenuItem.category_id == cat.id, MenuItem.is_available == True
    ).scalar() or 0
    data = CategoryResponse.model_validate(cat)
    data.item_count = count
    return data


def _serialize_item(item: MenuItem) -> MenuItemResponse:
    data = MenuItemResponse.model_validate(item)
    data.category_name = item.category.name if item.category else ""
    return data


@router.get("/categories", response_model=PaginatedResponse[CategoryResponse])
def list_categories(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Category).filter(Category.restaurant_id == current_user.restaurant_id).order_by(
        Category.display_order, Category.name
    )
    return paginate(q, page, page_size, lambda c: _serialize_category(c, db))


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Category).filter_by(restaurant_id=current_user.restaurant_id, name=body.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name already exists")
    cat = Category(restaurant_id=current_user.restaurant_id, **body.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _serialize_category(cat, db)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cat = db.get(Category, category_id)
    if not cat or cat.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return _serialize_category(cat, db)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cat = db.get(Category, category_id)
    if not cat or cat.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(cat)
    db.commit()
    return MessageResponse(message="Category deleted")


@router.get("/items", response_model=PaginatedResponse[MenuItemResponse])
def list_items(
    page: int = 1,
    page_size: int = 50,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    is_available: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MenuItem).filter(MenuItem.restaurant_id == current_user.restaurant_id)
    if category_id:
        q = q.filter(MenuItem.category_id == category_id)
    if is_available is not None:
        q = q.filter(MenuItem.is_available == is_available)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(MenuItem.name.ilike(term) | MenuItem.description.ilike(term))
    q = q.order_by(MenuItem.display_order, MenuItem.name)
    return paginate(q, page, page_size, _serialize_item)


@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    body: MenuItemCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cat = db.get(Category, body.category_id)
    if not cat or cat.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
    item = MenuItem(restaurant_id=current_user.restaurant_id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
def update_item(
    item_id: int,
    body: MenuItemUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.get(MenuItem, item_id)
    if not item or item.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.delete("/items/{item_id}", response_model=MessageResponse)
def delete_item(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.get(MenuItem, item_id)
    if not item or item.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    db.delete(item)
    db.commit()
    return MessageResponse(message="Menu item deleted")


@router.get("/public/{slug}", response_model=PublicMenuResponse)
def public_menu(slug: str, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter_by(slug=slug, is_active=True).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    categories = (
        db.query(Category)
        .filter(Category.restaurant_id == restaurant.id, Category.is_active == True)
        .order_by(Category.display_order, Category.name)
        .all()
    )

    menu = []
    for cat in categories:
        items = [PublicMenuItemResponse.model_validate(i) for i in cat.items if i.is_available]
        menu.append(PublicCategoryResponse(
            id=cat.id, name=cat.name, description=cat.description,
            display_order=cat.display_order, items=items,
        ))

    return PublicMenuResponse(
        restaurant={"id": restaurant.id, "name": restaurant.name,
                    "currency": restaurant.currency, "tax_rate": float(restaurant.tax_rate)},
        menu=menu,
    )
