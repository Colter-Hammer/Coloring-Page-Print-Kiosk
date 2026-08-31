import logging
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base, Page
from app.services.images import hash_saved_image_bytes

logger = logging.getLogger(__name__)


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


def _ensure_page_content_hash_column(engine) -> None:
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pages)").fetchall()}
        if "content_hash" not in cols:
            conn.exec_driver_sql("ALTER TABLE pages ADD COLUMN content_hash VARCHAR(64)")
            conn.commit()


def backfill_page_content_hashes(db: Session, images_dir: Path) -> None:
    """Compute and persist content_hash for any Page missing one, by hashing
    its already-saved full-res image's raw bytes off disk (comparable to
    compute_content_hash() — see its docstring for why raw saved bytes, not
    re-decoded pixels, are what's hashed). Idempotent (only touches rows
    where content_hash is NULL); a missing/unreadable file is logged and
    skipped rather than raised, so a bad row never blocks startup."""
    pages = db.query(Page).filter(Page.content_hash.is_(None)).all()
    for page in pages:
        try:
            file_bytes = (images_dir / page.image_path).read_bytes()
        except OSError as exc:
            logger.warning(
                "Skipping content-hash backfill for page id=%s (image_path=%s): %s",
                page.id, page.image_path, exc,
            )
            continue
        page.content_hash = hash_saved_image_bytes(file_bytes)
    db.commit()


def init_db() -> None:
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    for sub in ("category_icons", "pages/full", "pages/thumb", "pages/print_pdf"):
        Path(settings.images_dir, sub).mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_page_print_path_column(engine)
    _ensure_page_content_hash_column(engine)

    # Fine at kiosk scale (small library, synchronous startup); would need
    # chunking/async for a large library.
    session_local = get_session_local()
    db = session_local()
    try:
        backfill_page_content_hashes(db, Path(settings.images_dir))
    finally:
        db.close()
