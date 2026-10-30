import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.organizations.models import Organization, Plant


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored lower-cased; uniqueness is global because one person may belong to several tenants.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    preferred_language: Mapped[str] = mapped_column(String(5), default="es", server_default="es")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user")


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_code", ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    description: Mapped[str] = mapped_column(String(300))


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # System roles are shared by every tenant and cannot be edited by tenants.
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


plant_memberships = Table(
    "plant_memberships",
    Base.metadata,
    Column(
        "membership_id",
        ForeignKey("organization_memberships.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("plant_id", ForeignKey("plants.id", ondelete="CASCADE"), primary_key=True),
)


class OrganizationMembership(TimestampMixin, Base):
    """Links a user to an organization with one role.

    ``plants`` restricts the user to specific plants. An empty list means the user
    has access to every plant of the organization.
    """

    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(lazy="joined")
    role: Mapped[Role] = relationship(lazy="joined")
    plants: Mapped[list[Plant]] = relationship(secondary=plant_memberships, lazy="selectin")
