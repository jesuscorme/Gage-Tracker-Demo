"""API clients (machine-to-machine access with an API key).

A client acts through a dedicated service user that has its own membership, so every
existing rule applies unchanged: role permissions, plant scope, tenant isolation,
audit trail (the actor is the service user). The raw key is shown once; only its
SHA-256 is stored.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.logging import request_id_var
from app.core.security import hash_password
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import OrganizationMembership, Role, User
from app.modules.integrations.models import ApiClient, ApiRequestLog
from app.modules.organizations.models import Plant

KEY_PREFIX = "gtk_"
# Roles a machine client may receive (never organization administration).
CLIENT_ROLES = ("viewer", "auditor", "requester", "metrology_technician", "lab_technician", "edge_agent")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create(ctx: TenantContext, name: str, role_code: str, plant_ids: list[uuid.UUID],
           expires_at: datetime | None) -> tuple[ApiClient, str]:
    if role_code not in CLIENT_ROLES:
        raise BusinessRuleError(f"API clients may use one of {list(CLIENT_ROLES)}", code="invalid_role")
    role = ctx.db.scalar(select(Role).where(Role.code == role_code))
    plants = list(ctx.db.scalars(select(Plant).where(Plant.id.in_(plant_ids),
                                                     Plant.organization_id == ctx.organization_id)))
    if len(plants) != len(set(plant_ids)) or any(not ctx.can_access_plant(p.id) for p in plants):
        raise BusinessRuleError("Unknown plant", code="invalid_plant")
    if expires_at is not None and expires_at <= datetime.now(UTC):
        raise BusinessRuleError("expires_at must be in the future", code="invalid_date")
    prefix = secrets.token_hex(6)
    raw = f"{KEY_PREFIX}{prefix}_{secrets.token_urlsafe(32)}"
    user = User(email=f"api-{prefix}@service.invalid", full_name=f"API · {name}",
                password_hash=hash_password(secrets.token_urlsafe(48)), preferred_language="en")
    ctx.db.add(user)
    ctx.db.flush()
    m = OrganizationMembership(user_id=user.id, organization_id=ctx.organization_id, role_id=role.id)
    m.plants = plants
    ctx.db.add(m)
    client = ApiClient(organization_id=ctx.organization_id, name=name, user_id=user.id, key_prefix=prefix,
                       key_hash=_hash(raw), created_by=ctx.user_id, expires_at=expires_at)
    ctx.db.add(client)
    ctx.db.flush()
    ctx.audit(action="api_client.created", entity_type="api_client", entity_id=client.id,
              changes={"name": name, "role": role_code, "plants": [p.code for p in plants], "prefix": prefix,
                       "expires_at": expires_at.isoformat() if expires_at else None})
    ctx.db.commit()
    return client, raw


def get(ctx: TenantContext, client_id: uuid.UUID) -> ApiClient:
    c = ctx.db.scalar(select(ApiClient).where(ApiClient.id == client_id,
                                              ApiClient.organization_id == ctx.organization_id))
    if c is None:
        raise NotFoundError("API client not found")
    return c


def list_clients(ctx: TenantContext) -> list[ApiClient]:
    return list(ctx.db.scalars(select(ApiClient).where(ApiClient.organization_id == ctx.organization_id)
                               .order_by(ApiClient.created_at.desc())))


def revoke(ctx: TenantContext, client_id: uuid.UUID, reason: str) -> ApiClient:
    c = get(ctx, client_id)
    if c.revoked_at:
        raise ConflictError("Already revoked", code="invalid_status")
    c.revoked_at, c.revoked_reason = datetime.now(UTC), reason
    m = ctx.db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == c.user_id))
    m.is_active = False
    ctx.db.get(User, c.user_id).is_active = False
    ctx.audit(action="api_client.revoked", entity_type="api_client", entity_id=c.id, reason=reason,
              changes={"name": c.name, "prefix": c.key_prefix})
    ctx.db.commit()
    return c


def authenticate(db: Session, raw: str, method: str, path: str, ip: str | None) -> User | None:
    """Resolve an API key to its service user and record the call (request activity log)."""
    if not raw.startswith(KEY_PREFIX) or raw.count("_") < 2:
        return None
    prefix = raw[len(KEY_PREFIX):].split("_", 1)[0]
    client = db.scalar(select(ApiClient).where(ApiClient.key_prefix == prefix))
    if client is None or not hmac.compare_digest(client.key_hash, _hash(raw)):
        return None
    now = datetime.now(UTC)
    if client.revoked_at or (client.expires_at and client.expires_at <= now):
        return None
    user = db.get(User, client.user_id)
    if user is None or not user.is_active:
        return None
    client.last_used_at = now
    db.add(ApiRequestLog(organization_id=client.organization_id, client_id=client.id, method=method,
                         path=path[:300], request_id=request_id_var.get(), ip_address=ip))
    db.commit()
    return user


def activity(ctx: TenantContext, client_id: uuid.UUID, limit: int) -> list[ApiRequestLog]:
    get(ctx, client_id)
    return list(ctx.db.scalars(select(ApiRequestLog).where(ApiRequestLog.client_id == client_id)
                               .order_by(ApiRequestLog.requested_at.desc()).limit(limit)))
