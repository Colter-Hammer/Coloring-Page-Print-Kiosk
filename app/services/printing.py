import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from PIL import Image
from pyipp import IPP
from pyipp.enums import IppOperation
from pyipp.exceptions import IPPConnectionError, IPPError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import PrintLog
from app.services.images import flatten_to_white

PAGE_SIZES_INCHES = {
    "letter": (8.5, 11.0),
    "a4": (8.27, 11.69),
}

DPI = 150


class PrinterUnreachableError(Exception):
    """The printer could not be reached (offline, wrong IP, network error)."""


class PrinterJobError(Exception):
    """The printer was reached but rejected or failed the print job."""


class PrinterClient(Protocol):
    async def print_pdf(self, pdf_bytes: bytes, job_name: str) -> None: ...


CONNECT_TIMEOUT_SECONDS = 4


class IPPPrinterClient:
    """Sends a print job directly to a printer's IP over IPP (no CUPS)."""

    def __init__(self, printer_ip: str) -> None:
        self._printer_ip = printer_ip

    async def print_pdf(self, pdf_bytes: bytes, job_name: str) -> None:
        ipp = IPP(
            host=self._printer_ip,
            base_path="/ipp/print",
            request_timeout=CONNECT_TIMEOUT_SECONDS,
        )
        try:
            await ipp.execute(
                IppOperation.PRINT_JOB,
                {
                    "operation-attributes-tag": {
                        "document-format": "application/pdf",
                        "job-name": job_name,
                    },
                    "data": pdf_bytes,
                },
            )
        except IPPConnectionError as exc:
            raise PrinterUnreachableError(str(exc)) from exc
        except IPPError as exc:
            raise PrinterJobError(str(exc)) from exc
        finally:
            await ipp.close()


def image_to_pdf(image_path: Path, page_size: str = "letter") -> bytes:
    width_in, height_in = PAGE_SIZES_INCHES.get(page_size, PAGE_SIZES_INCHES["letter"])
    canvas_size = (round(width_in * DPI), round(height_in * DPI))

    with Image.open(image_path) as img:
        flattened = flatten_to_white(img)
        flattened.thumbnail(canvas_size)

        canvas = Image.new("RGB", canvas_size, "white")
        offset = (
            (canvas_size[0] - flattened.width) // 2,
            (canvas_size[1] - flattened.height) // 2,
        )
        canvas.paste(flattened, offset)

        buffer = io.BytesIO()
        canvas.save(buffer, format="PDF", resolution=DPI)
        return buffer.getvalue()


def get_recent_print_count(db: Session, window_hours: int = 1) -> int:
    """Counts ALL print_log rows (any status) in the trailing window.

    Counting every attempt, not just successes, is what stops repeated taps
    against a broken/offline printer from bypassing the rate limit.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=window_hours)
    return db.query(func.count(PrintLog.id)).filter(PrintLog.printed_at >= cutoff).scalar()


def is_rate_limited(db: Session, limit: int, window_hours: int = 1) -> bool:
    return get_recent_print_count(db, window_hours=window_hours) >= limit
