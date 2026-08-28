import io

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
