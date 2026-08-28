from datetime import UTC, datetime, timedelta

from app.models import Category, Page, PrintLog
from app.services.printing import get_recent_print_count, is_rate_limited


def _make_page(db_session) -> Page:
    category = Category(name="Animals", sort_order=0)
    db_session.add(category)
    db_session.flush()
    page = Page(category_id=category.id, image_path="a", thumb_path="b")
    db_session.add(page)
    db_session.commit()
    return page


def test_counts_all_statuses_within_window(db_session):
    page = _make_page(db_session)
    for status in ("success", "failed", "rate_limited"):
        db_session.add(PrintLog(page_id=page.id, status=status))
    db_session.commit()

    assert get_recent_print_count(db_session, window_hours=1) == 3


def test_rows_outside_window_are_not_counted(db_session):
    page = _make_page(db_session)
    old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    db_session.add(PrintLog(page_id=page.id, status="failed", printed_at=old_time))
    db_session.commit()

    assert get_recent_print_count(db_session, window_hours=1) == 0


def test_is_rate_limited_true_at_or_above_limit(db_session):
    page = _make_page(db_session)
    for _ in range(3):
        db_session.add(PrintLog(page_id=page.id, status="failed"))
    db_session.commit()

    assert is_rate_limited(db_session, limit=3) is True
    assert is_rate_limited(db_session, limit=4) is False
