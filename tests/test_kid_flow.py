import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import get_db
from app.deps import get_printer_client
from app.main import app
from app.models import Category, Page, PrintLog
from app.services.printing import PrinterUnreachableError


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed(db_session):
    c1 = Category(name="Animals", sort_order=1)
    c2 = Category(name="Dinosaurs", sort_order=2)
    db_session.add_all([c1, c2])
    db_session.flush()
    page = Page(
        category_id=c1.id,
        title="Lion",
        image_path="full/lion.png",
        thumb_path="thumb/lion.png",
    )
    db_session.add(page)
    db_session.commit()
    return c1, c2, page


def test_home_lists_categories_in_sort_order(client, db_session):
    _seed(db_session)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text.index("Animals") < response.text.index("Dinosaurs")


def test_category_lists_only_its_own_pages(client, db_session):
    c1, c2, page = _seed(db_session)
    response = client.get(f"/category/{c1.id}")
    assert response.status_code == 200
    assert f"/preview/{page.id}" in response.text

    response_empty = client.get(f"/category/{c2.id}")
    assert response_empty.status_code == 200
    assert f"/preview/{page.id}" not in response_empty.text


def test_preview_renders_expected_page_image(client, db_session):
    _c1, _c2, page = _seed(db_session)
    response = client.get(f"/preview/{page.id}")
    assert response.status_code == 200
    assert page.image_path in response.text


def test_category_back_link_returns_home(client, db_session):
    c1, _c2, _page = _seed(db_session)
    response = client.get(f"/category/{c1.id}")
    assert 'href="/"' in response.text


def test_preview_back_link_returns_to_category(client, db_session):
    c1, _c2, page = _seed(db_session)
    response = client.get(f"/preview/{page.id}")
    assert f'href="/category/{c1.id}"' in response.text


class FakePrinterClient:
    def __init__(self, should_raise: Exception | None = None):
        self.should_raise = should_raise
        self.calls: list[tuple[bytes, str]] = []

    async def print_pdf(self, pdf_bytes: bytes, job_name: str) -> None:
        self.calls.append((pdf_bytes, job_name))
        if self.should_raise:
            raise self.should_raise


def _seed_with_real_image(db_session, images_dir):
    category = Category(name="Animals", sort_order=1)
    db_session.add(category)
    db_session.flush()
    image_path = "pages/full/test.png"
    full_path = images_dir / image_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 200), "red").save(full_path, format="PNG")
    page = Page(category_id=category.id, image_path=image_path, thumb_path=image_path)
    db_session.add(page)
    db_session.commit()
    return category, page


def test_print_success_shows_confirmation_and_logs(db_session, images_dir):
    category, page = _seed_with_real_image(db_session, images_dir)
    fake_printer = FakePrinterClient()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_printer_client] = lambda: fake_printer
    with TestClient(app, follow_redirects=False) as test_client:
        response = test_client.post(f"/print/{page.id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "All done" in response.text
    assert f'hx-get="/category/{category.id}"' in response.text
    assert len(fake_printer.calls) == 1
    log = db_session.query(PrintLog).one()
    assert log.status == "success"


def test_print_printer_unreachable_shows_friendly_error_no_leak(db_session, images_dir):
    _category, page = _seed_with_real_image(db_session, images_dir)
    fake_printer = FakePrinterClient(
        should_raise=PrinterUnreachableError("connection refused to 10.0.0.99")
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_printer_client] = lambda: fake_printer
    with TestClient(app, follow_redirects=False) as test_client:
        response = test_client.post(f"/print/{page.id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "ask a grown-up" in response.text.lower()
    assert "PrinterUnreachableError" not in response.text
    assert "10.0.0.99" not in response.text
    log = db_session.query(PrintLog).one()
    assert log.status == "failed"


def test_print_rate_limited_never_calls_printer(db_session, images_dir):
    _category, page = _seed_with_real_image(db_session, images_dir)
    for _ in range(10):
        db_session.add(PrintLog(page_id=page.id, status="failed"))
    db_session.commit()

    fake_printer = FakePrinterClient()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_printer_client] = lambda: fake_printer
    with TestClient(app, follow_redirects=False) as test_client:
        response = test_client.post(f"/print/{page.id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "printed a lot" in response.text.lower()
    assert len(fake_printer.calls) == 0
    latest_log = db_session.query(PrintLog).order_by(PrintLog.id.desc()).first()
    assert latest_log.status == "rate_limited"
