import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dashboard_redirects_when_unauthenticated(client):
    response = client.get("/admin")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_login_wrong_password_shows_inline_error(client):
    response = client.post("/admin/login", data={"password": "nope"})
    assert response.status_code == 200
    assert "Incorrect password" in response.text
    assert "session" not in response.cookies


def test_login_correct_password_sets_session_and_redirects(client):
    response = client.post("/admin/login", data={"password": "test-admin-password"})
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert "session" in response.cookies


def test_authenticated_session_persists_across_requests(client):
    client.post("/admin/login", data={"password": "test-admin-password"})
    response = client.get("/admin")
    assert response.status_code == 200


def test_logout_clears_session(client):
    client.post("/admin/login", data={"password": "test-admin-password"})
    client.post("/admin/logout")
    response = client.get("/admin")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
