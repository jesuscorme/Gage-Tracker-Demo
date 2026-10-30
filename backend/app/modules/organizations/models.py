import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Days before the due date in which a gage is reported as "Due Soon".
    due_soon_days: Mapped[int] = mapped_column(Integer, default=30, server_default=text("30"))
    # IANA time zone used to decide "today" for due-date rules.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")

    plants: Mapped[list["Plant"]] = relationship(back_populates="organization")


class Plant(TimestampMixin, Base):
    __tablename__ = "plants"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    organization: Mapped[Organization] = relationship(back_populates="plants")


class Department(TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("plant_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
