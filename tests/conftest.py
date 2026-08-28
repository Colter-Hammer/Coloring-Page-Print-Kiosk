import os

os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("PRINTER_IP", "192.0.2.1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def images_dir(tmp_path, monkeypatch):
    """Redirect IMAGES_DIR to an isolated tmp_path for the duration of a test.

    Must be requested before any fixture that constructs a TestClient (which
    triggers the app's lifespan/init_db using the cached Settings), so the
    real ./data directory is never touched.
    """
    from app.config import get_settings

    monkeypatch.setenv("IMAGES_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
