import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_admin
from app.models import Category
from app.services.images import save_category_icon, validate_image
from app.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    settings = get_settings()
    if secrets.compare_digest(password, settings.admin_password):
        request.session["authenticated"] = True
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": "Incorrect password"}
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


def _ordered_categories(db: Session) -> list[Category]:
    return db.query(Category).order_by(Category.sort_order, Category.id).all()


@router.get("", dependencies=[Depends(require_admin)])
def dashboard(
    request: Request,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    error_message = "Move or delete the pages in this category first." if error == "category_has_pages" else None
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"categories": _ordered_categories(db), "error": error_message},
    )


@router.get("/categories/new", dependencies=[Depends(require_admin)])
def new_category_form(request: Request):
    return templates.TemplateResponse(
        request, "admin/category_form.html", {"category": None, "error": None}
    )


async def _validate_and_save_icon(icon: UploadFile | None) -> tuple[str | None, str | None]:
    """Returns (icon_path, error_message)."""
    if icon is None or not icon.filename:
        return None, None
    file_bytes = await icon.read()
    if not validate_image(file_bytes):
        return None, "Icon file is not a valid image"
    settings = get_settings()
    return save_category_icon(file_bytes, Path(settings.images_dir)), None


@router.post("/categories", dependencies=[Depends(require_admin)])
async def create_category(
    request: Request,
    name: str = Form(...),
    icon: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    icon_path, error = await _validate_and_save_icon(icon)
    if error:
        return templates.TemplateResponse(
            request, "admin/category_form.html", {"category": None, "error": error}, status_code=400
        )
    max_sort_order = db.query(func.max(Category.sort_order)).scalar() or 0
    category = Category(name=name, icon_image_path=icon_path, sort_order=max_sort_order + 1)
    db.add(category)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/categories/{category_id}/edit", dependencies=[Depends(require_admin)])
def edit_category_form(category_id: int, request: Request, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/category_form.html", {"category": category, "error": None}
    )


@router.post("/categories/{category_id}", dependencies=[Depends(require_admin)])
async def update_category(
    category_id: int,
    request: Request,
    name: str = Form(...),
    icon: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)
    icon_path, error = await _validate_and_save_icon(icon)
    if error:
        return templates.TemplateResponse(
            request, "admin/category_form.html", {"category": category, "error": error}, status_code=400
        )
    category.name = name
    if icon_path:
        category.icon_image_path = icon_path
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/categories/{category_id}/delete", dependencies=[Depends(require_admin)])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)
    if category.pages:
        return RedirectResponse(url="/admin?error=category_has_pages", status_code=303)
    db.delete(category)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


def _swap_sort_order(db: Session, category_id: int, direction: int) -> None:
    categories = _ordered_categories(db)
    idx = next((i for i, c in enumerate(categories) if c.id == category_id), None)
    if idx is None:
        return
    target = idx + direction
    if 0 <= target < len(categories):
        categories[idx].sort_order, categories[target].sort_order = (
            categories[target].sort_order,
            categories[idx].sort_order,
        )
        db.commit()


@router.post("/categories/{category_id}/move-up", dependencies=[Depends(require_admin)])
def move_category_up(category_id: int, db: Session = Depends(get_db)):
    _swap_sort_order(db, category_id, direction=-1)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/categories/{category_id}/move-down", dependencies=[Depends(require_admin)])
def move_category_down(category_id: int, db: Session = Depends(get_db)):
    _swap_sort_order(db, category_id, direction=1)
    return RedirectResponse(url="/admin", status_code=303)
