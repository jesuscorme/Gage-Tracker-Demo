"""Imports every model so Alembic and SQLAlchemy see the full metadata."""

from app.modules.audit.models import AuditEvent  # noqa: F401
from app.modules.gages.models import Gage, GageStatusHistory, GageType  # noqa: F401
from app.modules.identity.models import OrganizationMembership, Permission, Role, User  # noqa: F401
from app.modules.organizations.models import Department, Organization, Plant  # noqa: F401
