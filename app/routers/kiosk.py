from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Page
from app.templating import templates

router = APIRouter(tags=["kiosk"])


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.sort_order, Category.id).all()
    return templates.TemplateResponse(request, "kiosk/home.html", {"categories": categories})


@router.get("/category/{category_id}")
def category_view(category_id: int, request: Request, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)
    pages = (
        db.query(Page)
        .filter(Page.category_id == category_id)
        .order_by(Page.created_at)
        .all()
    )
    return templates.TemplateResponse(
        request, "kiosk/category.html", {"category": category, "pages": pages}
    )


@router.get("/preview/{page_id}")
def preview(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "kiosk/preview.html", {"page": page})
