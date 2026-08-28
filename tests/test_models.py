from app.models import Category, Page, PrintLog


def test_create_and_query_category(db_session):
    category = Category(name="Animals", sort_order=1)
    db_session.add(category)
    db_session.commit()

    fetched = db_session.query(Category).one()
    assert fetched.name == "Animals"
    assert fetched.sort_order == 1
    assert fetched.icon_image_path is None


def test_page_belongs_to_category(db_session):
    category = Category(name="Dinosaurs", sort_order=0)
    db_session.add(category)
    db_session.flush()

    page = Page(
        category_id=category.id,
        title="T-Rex",
        image_path="/img/full/trex.png",
        thumb_path="/img/thumb/trex.png",
        source="admin_upload",
    )
    db_session.add(page)
    db_session.commit()

    fetched_category = db_session.query(Category).one()
    assert len(fetched_category.pages) == 1
    assert fetched_category.pages[0].title == "T-Rex"


def test_print_log_records_status(db_session):
    category = Category(name="Space", sort_order=0)
    db_session.add(category)
    db_session.flush()
    page = Page(
        category_id=category.id,
        image_path="/img/full/rocket.png",
        thumb_path="/img/thumb/rocket.png",
    )
    db_session.add(page)
    db_session.flush()

    log = PrintLog(page_id=page.id, status="success")
    db_session.add(log)
    db_session.commit()

    fetched = db_session.query(PrintLog).one()
    assert fetched.status == "success"
    assert fetched.page_id == page.id


def test_deleting_category_cascades_pages(db_session):
    category = Category(name="Vehicles", sort_order=0)
    page = Page(
        category=category,
        image_path="/img/full/car.png",
        thumb_path="/img/thumb/car.png",
    )
    db_session.add(category)
    db_session.add(page)
    db_session.commit()

    db_session.delete(category)
    db_session.commit()

    assert db_session.query(Page).count() == 0
