"""Human-readable document numbers (CAL-2026-00001, WO-2026-00042, ...).

One counter per organization, prefix and year, incremented with a row lock so
concurrent requests never get the same number.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class CodeSequence(Base):
    __tablename__ = "code_sequences"
    __table_args__ = (UniqueConstraint("organization_id", "prefix", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    prefix: Mapped[str] = mapped_column(String(10))
    year: Mapped[int] = mapped_column(Integer)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


def next_code(db: Session, organization_id: uuid.UUID, prefix: str, year: int) -> str:
    db.execute(
        insert(CodeSequence)
        .values(organization_id=organization_id, prefix=prefix, year=year, last_value=0)
        .on_conflict_do_nothing(index_elements=["organization_id", "prefix", "year"])
    )
    seq = db.scalar(
        select(CodeSequence)
        .where(CodeSequence.organization_id == organization_id, CodeSequence.prefix == prefix,
               CodeSequence.year == year)
        .with_for_update()
    )
    seq.last_value += 1
    db.flush()
    return f"{prefix}-{year}-{seq.last_value:05d}"
