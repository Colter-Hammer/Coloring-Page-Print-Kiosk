from fastapi import Request

from app.db import get_db as get_db  # re-exported for router imports


class NotAuthenticated(Exception):
    """Raised by require_admin; handled by main.py to redirect to /admin/login."""


def require_admin(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise NotAuthenticated()
