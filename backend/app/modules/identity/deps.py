"""Authentication and tenant-context dependencies.

Every tenant-owned endpoint depends on :func:`require`, which resolves:

1. the authenticated user (Bearer token),
2. the active organization (``X-Organization-Id`` header, or the user's only membership),
3. the permissions granted by the membership's role,
4. the plants the membership may access (empty list = every plant).

Services must filter every query by ``ctx.organization_id`` and check plant scope with
:meth:`TenantContext.can_access_plant`. Resources outside the tenant are reported as
"not found" so that their existence is not disclosed.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AuthenticationError, BusinessRuleError, PermissionDeniedError
from app.core.security import decode_access_token
from app.modules.audit import service as audit
from app.modules.identity.models import OrganizationMembership, User
from app.modules.organizations.models import Organization

bearer = HTTPBearer(auto_error=False)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, max_length=200),
    db: Session = Depends(get_db),
) -> User:
    if creds is None and x_api_key:
        # Machine clients (app/modules/integrations/api_clients.py).
        from app.modules.integrations.api_clients import authenticate

        user = authenticate(db, x_api_key, request.method, request.url.path, _client_ip(request))
        if user is None:
            raise AuthenticationError("Invalid, expired or revoked API key", code="invalid_api_key")
        return user
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    decoded = decode_access_token(creds.credentials)
    if decoded is None:
        raise AuthenticationError("Invalid or expired token", code="invalid_token")
    user_id, version = decoded
    user = db.get(User, user_id)
    # A token issued before a logout-all / password change has an old version.
    if user is None or not user.is_active or version != user.token_version:
        raise AuthenticationError("Invalid or expired token", code="invalid_token")
    return user


@dataclass
class TenantContext:
    db: Session
    user: User
    membership: OrganizationMembership
    organization: Organization
    permissions: frozenset[str]
    # None means "all plants of the organization".
    plant_ids: frozenset[uuid.UUID] | None
    ip_address: str | None = None
    _today: date | None = field(default=None, repr=False)

    @property
    def organization_id(self) -> uuid.UUID:
        return self.organization.id

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def ensure(self, permission: str) -> None:
        if permission not in self.permissions:
            raise PermissionDeniedError(
                "You do not have permission to perform this action",
                details={"required_permission": permission},
            )

    def can_access_plant(self, plant_id: uuid.UUID) -> bool:
        return self.plant_ids is None or plant_id in self.plant_ids

    def today(self) -> date:
        """Current date in the organization's time zone (used for due-date rules)."""
        if self._today is None:
            self._today = datetime.now(ZoneInfo(self.organization.timezone)).date()
        return self._today

    def audit(self, **kwargs) -> None:
        audit.record(
            self.db,
            organization_id=self.organization_id,
            actor_user_id=self.user_id,
            ip_address=self.ip_address,
            **kwargs,
        )


def get_tenant_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_organization_id: str | None = Header(default=None),
) -> TenantContext:
    stmt = select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True)
    )
    if x_organization_id:
        try:
            org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise BusinessRuleError("Invalid X-Organization-Id header", code="invalid_organization")
        membership = db.scalars(stmt.where(OrganizationMembership.organization_id == org_id)).first()
        if membership is None:
            raise PermissionDeniedError(
                "You are not a member of this organization", code="organization_access_denied"
            )
    else:
        memberships = list(db.scalars(stmt))
        if len(memberships) != 1:
            raise BusinessRuleError(
                "Select an organization with the X-Organization-Id header",
                code="organization_required",
            )
        membership = memberships[0]

    org = membership.organization
    if not org.is_active:
        raise PermissionDeniedError("Organization is inactive", code="organization_inactive")

    plant_ids = frozenset(p.id for p in membership.plants) or None
    return TenantContext(
        db=db,
        user=user,
        membership=membership,
        organization=org,
        permissions=frozenset(p.code for p in membership.role.permissions),
        plant_ids=plant_ids,
        ip_address=_client_ip(request),
    )


def require(*permissions: str) -> Callable[..., TenantContext]:
    """Dependency factory: tenant context + all the given permissions."""

    def _dep(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        for perm in permissions:
            ctx.ensure(perm)
        return ctx

    return _dep
