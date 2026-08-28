import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_printer_client
from app.models import Category, Page, PrintLog
from app.services.printing import PrinterClient, image_to_pdf, is_rate_limited
from app.templating import templates

logger = logging.getLogger(__name__)

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


@router.post("/print/{page_id}")
async def print_page(
    page_id: int,
    request: Request,
    db: Session = Depends(get_db),
    printer_client: PrinterClient = Depends(get_printer_client),
):
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404)

    settings = get_settings()

    if is_rate_limited(db, limit=settings.print_rate_limit_per_hour):
        db.add(PrintLog(page_id=page_id, status="rate_limited"))
        db.commit()
        return templates.TemplateResponse(
            request, "kiosk/_print_error.html", {"page": page, "reason": "rate_limit"}
        )

    images_dir = Path(settings.images_dir)
    try:
        pdf_bytes = image_to_pdf(images_dir / page.image_path, page_size=settings.page_size)
        await printer_client.print_pdf(pdf_bytes, job_name=page.title or f"page-{page.id}")
    except Exception:
        logger.exception("Print failed for page_id=%s", page_id)
        db.add(PrintLog(page_id=page_id, status="failed"))
        db.commit()
        return templates.TemplateResponse(
            request, "kiosk/_print_error.html", {"page": page, "reason": "printer"}
        )

    db.add(PrintLog(page_id=page_id, status="success"))
    db.commit()
    return templates.TemplateResponse(request, "kiosk/_print_success.html", {"page": page})
