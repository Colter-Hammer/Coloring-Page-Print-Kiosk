from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import init_db
from app.deps import NotAuthenticated
from app.routers import admin

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    fastapi_app = FastAPI(title="Coloring Kiosk", lifespan=lifespan)
    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    fastapi_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    images_dir = Path(settings.images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    fastapi_app.mount("/media", StaticFiles(directory=str(images_dir)), name="media")

    @fastapi_app.exception_handler(NotAuthenticated)
    async def _not_authenticated_handler(request: Request, exc: NotAuthenticated):
        return RedirectResponse(url="/admin/login", status_code=303)

    fastapi_app.include_router(admin.router)

    return fastapi_app


app = create_app()
