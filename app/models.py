from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon_image_path: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="admin_upload")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    category: Mapped["Category"] = relationship(back_populates="pages")


class PrintLog(Base):
    __tablename__ = "print_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), nullable=False)
    printed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
