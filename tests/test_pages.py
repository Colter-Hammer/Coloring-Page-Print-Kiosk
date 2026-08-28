import io

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import get_db
from app.main import app
from app.models import Category, Page


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, follow_redirects=False) as test_client:
        test_client.post("/admin/login", data={"password": "test-admin-password"})
        yield test_client
    app.dependency_overrides.clear()


def _png_bytes(color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_category(db_session, name="Animals") -> Category:
    category = Category(name=name, sort_order=0)
    db_session.add(category)
    db_session.commit()
    return category


def _pdf_bytes(page_count: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(page_count):
        page = doc.new_page(width=200, height=200)
        page.draw_rect(pymupdf.Rect(20, 20, 180, 180), color=(1, 0, 0), fill=(1, 0, 0))
    data = doc.tobytes()
    doc.close()
    return data


def test_bulk_upload_creates_pages_and_thumbnails(client, db_session, images_dir):
    category = _make_category(db_session)

    response = client.post(
        f"/admin/categories/{category.id}/pages",
        files=[
            ("files", ("a.png", _png_bytes("red"), "image/png")),
            ("files", ("b.png", _png_bytes("blue"), "image/png")),
        ],
    )
    assert response.status_code == 303

    pages = db_session.query(Page).filter_by(category_id=category.id).all()
    assert len(pages) == 2
    for page in pages:
        full_path = images_dir / page.image_path
        thumb_path = images_dir / page.thumb_path
        assert full_path.exists()
        assert thumb_path.exists()
        with Image.open(thumb_path) as img:
            assert max(img.size) <= 300


def test_bulk_upload_skips_invalid_file_without_failing_batch(client, db_session, images_dir):
    category = _make_category(db_session)

    response = client.post(
        f"/admin/categories/{category.id}/pages",
        files=[
            ("files", ("a.png", _png_bytes("red"), "image/png")),
            ("files", ("not-an-image.txt", b"hello world", "text/plain")),
        ],
    )
    assert response.status_code == 303

    pages = db_session.query(Page).filter_by(category_id=category.id).all()
    assert len(pages) == 1


def test_bulk_upload_accepts_single_page_pdf(client, db_session, images_dir):
    category = _make_category(db_session)

    response = client.post(
        f"/admin/categories/{category.id}/pages",
        files=[("files", ("sheet.pdf", _pdf_bytes(1), "application/pdf"))],
    )
    assert response.status_code == 303

    page = db_session.query(Page).filter_by(category_id=category.id).one()
    assert page.print_path is not None
    print_path = images_dir / page.print_path
    assert print_path.exists()
    assert print_path.read_bytes().startswith(b"%PDF")

    full_path = images_dir / page.image_path
    thumb_path = images_dir / page.thumb_path
    assert full_path.exists()
    with Image.open(full_path) as img:
        assert max(img.size) <= 2000
    with Image.open(thumb_path) as img:
        assert max(img.size) <= 300


def test_bulk_upload_rejects_multi_page_pdf(client, db_session, images_dir):
    category = _make_category(db_session)

    response = client.post(
        f"/admin/categories/{category.id}/pages",
        files=[("files", ("sheet.pdf", _pdf_bytes(2), "application/pdf"))],
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "skipped" in response.text.lower()

    pages = db_session.query(Page).filter_by(category_id=category.id).all()
    assert len(pages) == 0


def test_bulk_upload_rejects_corrupt_pdf(client, db_session, images_dir):
    category = _make_category(db_session)

    response = client.post(
        f"/admin/categories/{category.id}/pages",
        files=[("files", ("sheet.pdf", b"%PDF-1.4\nnot really a pdf", "application/pdf"))],
    )
    assert response.status_code == 303

    pages = db_session.query(Page).filter_by(category_id=category.id).all()
    assert len(pages) == 0


def test_delete_page_removes_row_and_files(client, db_session, images_dir):
    category = _make_category(db_session)
    client.post(
        f"/admin/categories/{category.id}/pages",
        files=[("files", ("a.png", _png_bytes(), "image/png"))],
    )
    page = db_session.query(Page).one()
    full_path = images_dir / page.image_path
    thumb_path = images_dir / page.thumb_path
    assert full_path.exists()

    response = client.post(f"/admin/pages/{page.id}/delete")
    assert response.status_code == 303
    assert db_session.query(Page).count() == 0
    assert not full_path.exists()
    assert not thumb_path.exists()


def test_delete_pdf_sourced_page_removes_print_path_file(client, db_session, images_dir):
    category = _make_category(db_session)
    client.post(
        f"/admin/categories/{category.id}/pages",
        files=[("files", ("sheet.pdf", _pdf_bytes(1), "application/pdf"))],
    )
    page = db_session.query(Page).one()
    print_path = images_dir / page.print_path
    assert print_path.exists()

    response = client.post(f"/admin/pages/{page.id}/delete")
    assert response.status_code == 303
    assert db_session.query(Page).count() == 0
    assert not print_path.exists()


def test_recategorize_page_moves_it_to_new_category(client, db_session, images_dir):
    category_a = _make_category(db_session, "Animals")
    category_b = _make_category(db_session, "Dinosaurs")
    client.post(
        f"/admin/categories/{category_a.id}/pages",
        files=[("files", ("a.png", _png_bytes(), "image/png"))],
    )
    page = db_session.query(Page).one()

    response = client.post(
        f"/admin/pages/{page.id}/recategorize", data={"category_id": category_b.id}
    )
    assert response.status_code == 303
    db_session.refresh(page)
    assert page.category_id == category_b.id
