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


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_create_category_without_icon(client, db_session):
    response = client.post("/admin/categories", data={"name": "Animals"})
    assert response.status_code == 303
    category = db_session.query(Category).one()
    assert category.name == "Animals"
    assert category.icon_image_path is None
    assert category.sort_order == 1


def test_create_category_with_icon_stores_resized_file(db_session, images_dir):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, follow_redirects=False) as test_client:
        test_client.post("/admin/login", data={"password": "test-admin-password"})
        response = test_client.post(
            "/admin/categories",
            data={"name": "Dinosaurs"},
            files={"icon": ("icon.png", _png_bytes(), "image/png")},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 303
    category = db_session.query(Category).one()
    assert category.icon_image_path is not None
    assert (images_dir / category.icon_image_path).exists()


def test_categories_ordered_by_sort_order_on_dashboard(client, db_session):
    client.post("/admin/categories", data={"name": "First"})
    client.post("/admin/categories", data={"name": "Second"})
    response = client.get("/admin")
    assert response.text.index("First") < response.text.index("Second")


def test_move_up_swaps_sort_order(client, db_session):
    client.post("/admin/categories", data={"name": "First"})
    client.post("/admin/categories", data={"name": "Second"})
    second = db_session.query(Category).filter_by(name="Second").one()

    response = client.post(f"/admin/categories/{second.id}/move-up")
    assert response.status_code == 303

    ordered = db_session.query(Category).order_by(Category.sort_order).all()
    assert [c.name for c in ordered] == ["Second", "First"]


def test_move_up_on_first_category_is_noop(client, db_session):
    client.post("/admin/categories", data={"name": "First"})
    client.post("/admin/categories", data={"name": "Second"})
    first = db_session.query(Category).filter_by(name="First").one()

    client.post(f"/admin/categories/{first.id}/move-up")

    ordered = db_session.query(Category).order_by(Category.sort_order).all()
    assert [c.name for c in ordered] == ["First", "Second"]


def test_move_down_on_last_category_is_noop(client, db_session):
    client.post("/admin/categories", data={"name": "First"})
    client.post("/admin/categories", data={"name": "Second"})
    second = db_session.query(Category).filter_by(name="Second").one()

    client.post(f"/admin/categories/{second.id}/move-down")

    ordered = db_session.query(Category).order_by(Category.sort_order).all()
    assert [c.name for c in ordered] == ["First", "Second"]


def test_edit_category_updates_name(client, db_session):
    client.post("/admin/categories", data={"name": "Origional"})
    category = db_session.query(Category).one()

    response = client.post(f"/admin/categories/{category.id}", data={"name": "Original"})
    assert response.status_code == 303
    db_session.refresh(category)
    assert category.name == "Original"


def test_delete_category_without_pages_succeeds(client, db_session):
    client.post("/admin/categories", data={"name": "Empty"})
    category = db_session.query(Category).one()

    response = client.post(f"/admin/categories/{category.id}/delete")
    assert response.status_code == 303
    assert db_session.query(Category).count() == 0


def test_delete_category_with_pages_is_blocked(client, db_session):
    client.post("/admin/categories", data={"name": "Has Pages"})
    category = db_session.query(Category).one()
    page = Page(category_id=category.id, image_path="a", thumb_path="b")
    db_session.add(page)
    db_session.commit()

    response = client.post(f"/admin/categories/{category.id}/delete")
    assert response.status_code == 303
    assert db_session.query(Category).count() == 1

    dashboard = client.get(response.headers["location"])
    assert "Move or delete the pages" in dashboard.text
