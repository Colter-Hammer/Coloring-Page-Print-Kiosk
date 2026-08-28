import io

import pytest
from PIL import Image

from app.services.printing import (
    IPPPrinterClient,
    PrinterJobError,
    PrinterUnreachableError,
    image_to_pdf,
)


def _make_test_image(tmp_path, mode="RGBA", color=(255, 0, 0, 128)):
    path = tmp_path / "source.png"
    Image.new(mode, (400, 300), color).save(path, format="PNG")
    return path


def test_image_to_pdf_produces_valid_pdf_bytes(tmp_path):
    image_path = _make_test_image(tmp_path)
    pdf_bytes = image_to_pdf(image_path, page_size="letter")
    assert pdf_bytes.startswith(b"%PDF")


def test_image_to_pdf_handles_transparent_images(tmp_path):
    image_path = _make_test_image(tmp_path, mode="RGBA", color=(0, 255, 0, 0))
    pdf_bytes = image_to_pdf(image_path, page_size="a4")
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_ipp_printer_client_raises_unreachable_on_connection_error(monkeypatch):
    from pyipp.exceptions import IPPConnectionError

    class FakeIPP:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, operation, message):
            raise IPPConnectionError("boom")

        async def close(self):
            pass

    monkeypatch.setattr("app.services.printing.IPP", FakeIPP)

    client = IPPPrinterClient("192.0.2.1")
    with pytest.raises(PrinterUnreachableError):
        await client.print_pdf(b"%PDF-fake", "Test Job")


@pytest.mark.asyncio
async def test_ipp_printer_client_raises_job_error_on_ipp_error(monkeypatch):
    from pyipp.exceptions import IPPError

    class FakeIPP:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, operation, message):
            raise IPPError("rejected")

        async def close(self):
            pass

    monkeypatch.setattr("app.services.printing.IPP", FakeIPP)

    client = IPPPrinterClient("192.0.2.1")
    with pytest.raises(PrinterJobError):
        await client.print_pdf(b"%PDF-fake", "Test Job")


@pytest.mark.asyncio
async def test_ipp_printer_client_succeeds_and_sends_pdf_data(monkeypatch):
    captured = {}

    class FakeIPP:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, operation, message):
            captured["operation"] = operation
            captured["message"] = message
            return {"status-code": 0}

        async def close(self):
            pass

    monkeypatch.setattr("app.services.printing.IPP", FakeIPP)

    client = IPPPrinterClient("192.0.2.1")
    await client.print_pdf(b"%PDF-fake", "Test Job")

    assert captured["message"]["data"] == b"%PDF-fake"
