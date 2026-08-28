from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


@lru_cache
def get_engine():
    settings = get_settings()
    return create_engine(
        f"sqlite:///{settings.database_path}",
        connect_args={"check_same_thread": False},
    )


def get_session_local():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db():
    session_local = get_session_local()
    db: Session = session_local()
    try:
        yield db
    finally:
        db.close()


def _ensure_page_print_path_column(engine) -> None:
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pages)").fetchall()}
        if "print_path" not in cols:
            conn.exec_driver_sql("ALTER TABLE pages ADD COLUMN print_path VARCHAR(500)")
            conn.commit()


def init_db() -> None:
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    for sub in ("category_icons", "pages/full", "pages/thumb", "pages/print_pdf"):
        Path(settings.images_dir, sub).mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_page_print_path_column(engine)
