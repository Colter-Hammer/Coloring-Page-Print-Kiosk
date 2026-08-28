from fastapi import Request

from app.config import get_settings
from app.db import get_db as get_db  # re-exported for router imports
from app.services.printing import IPPPrinterClient, PrinterClient


class NotAuthenticated(Exception):
    """Raised by require_admin; handled by main.py to redirect to /admin/login."""


def require_admin(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise NotAuthenticated()


def get_printer_client() -> PrinterClient:
    settings = get_settings()
    return IPPPrinterClient(settings.printer_ip)
