import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Category, Page


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
