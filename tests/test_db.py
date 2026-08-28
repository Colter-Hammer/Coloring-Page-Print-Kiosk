from sqlalchemy import create_engine

from app.db import _ensure_page_print_path_column


def _make_pre_change_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE pages (
                id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                title VARCHAR(200),
                image_path VARCHAR(500) NOT NULL,
                thumb_path VARCHAR(500) NOT NULL,
                source VARCHAR(20) NOT NULL,
                created_at DATETIME
            )
            """
        )
        conn.commit()
    return engine


def _column_names(engine) -> set[str]:
    with engine.connect() as conn:
        return {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pages)").fetchall()}


def test_ensure_page_print_path_column_adds_missing_column():
    engine = _make_pre_change_engine()
    assert "print_path" not in _column_names(engine)

    _ensure_page_print_path_column(engine)

    assert "print_path" in _column_names(engine)


def test_ensure_page_print_path_column_is_idempotent():
    engine = _make_pre_change_engine()

    _ensure_page_print_path_column(engine)
    _ensure_page_print_path_column(engine)

    assert "print_path" in _column_names(engine)
