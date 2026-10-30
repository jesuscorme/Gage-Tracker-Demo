import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

CATEGORIES = ("PHOTO", "DOCUMENT", "CERTIFICATE", "EVIDENCE", "REPORT")


class Attachment(Base):
    """Metadata of a stored file linked to a business record.

    Files are immutable. A document can be withdrawn (logical removal with reason) unless
    it is locked because it supports an approved record (certificate, issued report...).
    """

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_entity", "organization_id", "entity_type", "entity_id"),
        CheckConstraint(f"category IN {CATEGORIES}", name="category_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID]
    category: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    removal_reason: Mapped[str | None] = mapped_column(String(500))
