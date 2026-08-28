import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.deps import require_admin
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


@router.get("", dependencies=[Depends(require_admin)])
def dashboard(request: Request):
    return templates.TemplateResponse(request, "admin/dashboard.html", {})
