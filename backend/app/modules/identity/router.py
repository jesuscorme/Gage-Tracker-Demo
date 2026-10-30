import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import (
    TooManyRequestsError,
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.audit import service as audit
from app.modules.audit.models import AuditEvent
from app.modules.identity.deps import TenantContext, get_current_user, require
from app.modules.identity.models import OrganizationMembership, PasswordResetToken, Role, User
from app.modules.identity.permissions import P
from app.modules.identity.schemas import (
    _check_password,
    LoginRequest,
    MembershipOut,
    MeOut,
    MeUpdate,
    OrgUserOut,
    PlantRef,
    RegisterRequest,
    RoleOut,
    TokenResponse,
    UserCreate,
    UserUpdate,
)
from app.modules.organizations.models import Organization, Plant

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(tags=["users"])

# Used to keep login timing similar whether or not the e-mail exists.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password-1")
ADMIN_ROLE = "org_admin"


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "org"
    return f"{base}-{secrets.token_hex(3)}"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        preferred_language=user.preferred_language,
        memberships=[
            MembershipOut(
                organization_id=m.organization_id,
                organization_name=m.organization.name,
                role_code=m.role.code,
                role_name=m.role.name,
                permissions=sorted(p.code for p in m.role.permissions),
                plants=[PlantRef.model_validate(p) for p in m.plants],
            )
            for m in user.memberships
            if m.is_active and m.organization.is_active
        ],
    )


@auth_router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Create a new organization, its first plant and its first administrator."""
    if not get_settings().allow_self_registration:
        raise PermissionDeniedError("Self registration is disabled", code="registration_disabled")
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise BusinessRuleError("Unknown time zone", code="invalid_timezone")

    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this e-mail already exists", code="email_taken")

    org = Organization(name=body.organization_name.strip(), slug=_slugify(body.organization_name), timezone=body.timezone)
    db.add(org)
    db.flush()
    plant = Plant(organization_id=org.id, code=body.plant_code.strip().upper(), name=body.plant_name.strip())
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        preferred_language=body.preferred_language,
    )
    db.add_all([plant, user])
    db.flush()
    role = db.scalar(select(Role).where(Role.code == ADMIN_ROLE))
    db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role_id=role.id))

    ip = _client_ip(request)
    for action, etype, eid, changes in (
        ("organization.created", "organization", org.id, {"name": org.name}),
        ("plant.created", "plant", plant.id, {"code": plant.code, "name": plant.name}),
        ("user.registered", "user", user.id, {"email": email, "role": ADMIN_ROLE}),
    ):
        audit.record(
            db, action=action, entity_type=etype, entity_id=eid, organization_id=org.id,
            actor_user_id=user.id, changes=changes, ip_address=ip,
        )
    db.commit()
    token, ttl = create_access_token(user.id, user.token_version or 0)
    return TokenResponse(access_token=token, expires_in=ttl)


def _recent_failures(db: Session, user: User) -> int:
    s = get_settings()
    since = datetime.now(UTC) - timedelta(minutes=s.login_lockout_minutes)
    last_ok = db.scalar(select(func.max(AuditEvent.created_at)).where(
        AuditEvent.entity_type == "user", AuditEvent.entity_id == str(user.id),
        AuditEvent.action.in_(("auth.login", "auth.password_reset"))))
    if last_ok and last_ok > since:
        since = last_ok
    return db.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.entity_type == "user", AuditEvent.entity_id == str(user.id),
        AuditEvent.action == "auth.login_failed", AuditEvent.created_at > since)) or 0


@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and _recent_failures(db, user) >= get_settings().login_max_failures:
        audit.record(db, action="auth.login_locked", entity_type="user", entity_id=user.id,
                     actor_user_id=user.id, ip_address=_client_ip(request))
        db.commit()
        raise TooManyRequestsError("Too many failed attempts. Try again later or ask an administrator for a "
                                   "reset link.", code="too_many_attempts")
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        if user:
            audit.record(
                db, action="auth.login_failed", entity_type="user", entity_id=user.id,
                actor_user_id=user.id, ip_address=_client_ip(request),
            )
            db.commit()
        raise AuthenticationError("Invalid e-mail or password", code="invalid_credentials")
    user.last_login_at = datetime.now(UTC)
    audit.record(
        db, action="auth.login", entity_type="user", entity_id=user.id,
        actor_user_id=user.id, ip_address=_client_ip(request),
    )
    db.commit()
    token, ttl = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, expires_in=ttl)


@auth_router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return _me(user)


@auth_router.patch("/me", response_model=MeOut)
def update_me(body: MeUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    before = audit.snapshot(user, list(data))
    for k, v in data.items():
        setattr(user, k, v)
    changes = audit.diff(before, data)
    if changes:
        audit.record(db, action="user.profile_updated", entity_type="user", entity_id=user.id,
                     actor_user_id=user.id, changes=changes)
    db.commit()
    db.refresh(user)
    return _me(user)


# ---------------------------------------------------------------- organization users


def _user_out(m: OrganizationMembership) -> OrgUserOut:
    return OrgUserOut(
        id=m.user.id,
        email=m.user.email,
        full_name=m.user.full_name,
        role_code=m.role.code,
        role_name=m.role.name,
        is_active=m.is_active and m.user.is_active,
        plants=[PlantRef.model_validate(p) for p in m.plants],
        last_login_at=m.user.last_login_at,
    )


def _resolve_role(db: Session, code: str) -> Role:
    role = db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise BusinessRuleError("Unknown role", code="invalid_role", details={"role_code": code})
    return role


def _resolve_plants(ctx: TenantContext, plant_ids: list[uuid.UUID]) -> list[Plant]:
    if not plant_ids:
        return []
    plants = list(
        ctx.db.scalars(
            select(Plant).where(Plant.organization_id == ctx.organization_id, Plant.id.in_(plant_ids))
        )
    )
    if len(plants) != len(set(plant_ids)):
        raise BusinessRuleError("One or more plants do not exist", code="invalid_plant")
    return plants


def _membership(ctx: TenantContext, user_id: uuid.UUID) -> OrganizationMembership:
    m = ctx.db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == ctx.organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if m is None:
        raise NotFoundError("User not found")
    return m


def _active_admin_count(ctx: TenantContext) -> int:
    return ctx.db.scalar(
        select(func.count())
        .select_from(OrganizationMembership)
        .join(Role)
        .where(
            OrganizationMembership.organization_id == ctx.organization_id,
            OrganizationMembership.is_active.is_(True),
            Role.code == ADMIN_ROLE,
        )
    )


@users_router.get("/roles", response_model=list[RoleOut])
def list_roles(ctx: TenantContext = Depends(require(P.USERS_READ))):
    roles = ctx.db.scalars(select(Role).where(Role.is_system.is_(True)).order_by(Role.name))
    return [RoleOut(code=r.code, name=r.name, permissions=sorted(p.code for p in r.permissions)) for r in roles]


@users_router.get("/users", response_model=list[OrgUserOut])
def list_users(ctx: TenantContext = Depends(require(P.USERS_READ))):
    ms = ctx.db.scalars(
        select(OrganizationMembership)
        .join(User)
        .where(OrganizationMembership.organization_id == ctx.organization_id)
        .order_by(User.full_name)
    )
    return [_user_out(m) for m in ms]


@users_router.post("/users", response_model=OrgUserOut, status_code=201)
def create_user(body: UserCreate, ctx: TenantContext = Depends(require(P.USERS_MANAGE))):
    db = ctx.db
    role = _resolve_role(db, body.role_code)
    plants = _resolve_plants(ctx, body.plant_ids)
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password))
        db.add(user)
        db.flush()
    elif db.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == ctx.organization_id,
        )
    ):
        raise ConflictError("The user already belongs to this organization", code="already_member")

    m = OrganizationMembership(user_id=user.id, organization_id=ctx.organization_id, role_id=role.id)
    m.plants = plants
    db.add(m)
    db.flush()
    ctx.audit(
        action="user.added", entity_type="user", entity_id=user.id,
        changes={"email": email, "role": role.code, "plants": [p.code for p in plants]},
    )
    db.commit()
    db.refresh(m)
    return _user_out(m)


@users_router.patch("/users/{user_id}", response_model=OrgUserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, ctx: TenantContext = Depends(require(P.USERS_MANAGE))):
    db = ctx.db
    m = _membership(ctx, user_id)
    before = {"role": m.role.code, "plants": sorted(p.code for p in m.plants), "is_active": m.is_active}

    if body.role_code is not None:
        m.role = _resolve_role(db, body.role_code)
    if body.plant_ids is not None:
        m.plants = _resolve_plants(ctx, body.plant_ids)
    if body.is_active is not None:
        m.is_active = body.is_active
    db.flush()

    # Never leave the organization without an active administrator.
    if _active_admin_count(ctx) == 0:
        db.rollback()
        raise BusinessRuleError(
            "The organization must keep at least one active administrator", code="last_admin"
        )

    after = {"role": m.role.code, "plants": sorted(p.code for p in m.plants), "is_active": m.is_active}
    changes = audit.diff(before, after)
    if changes:
        ctx.audit(action="user.membership_updated", entity_type="user", entity_id=user_id, changes=changes)
    db.commit()
    db.refresh(m)
    return _user_out(m)


# ---------------------------------------------------------------- sessions and passwords


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class ResetIssued(BaseModel):
    reset_token: str
    expires_at: datetime


@auth_router.post("/change-password", response_model=TokenResponse)
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    audit.record(db, action="auth.password_changed", entity_type="user", entity_id=user.id, actor_user_id=user.id,
                 ip_address=_client_ip(request))
    db.commit()
    token, ttl = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, expires_in=ttl)


@auth_router.post("/logout-all", status_code=204)
def logout_all(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke every token issued to the user (all devices)."""
    user.token_version = (user.token_version or 0) + 1
    audit.record(db, action="auth.logout_all", entity_type="user", entity_id=user.id, actor_user_id=user.id,
                 ip_address=_client_ip(request))
    db.commit()


@auth_router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    digest = hashlib.sha256(body.token.encode()).hexdigest()
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest).with_for_update())
    if row is None or row.used_at is not None or row.expires_at <= datetime.now(UTC):
        raise BusinessRuleError("The reset link is invalid or has expired", code="invalid_reset_token")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise BusinessRuleError("The reset link is invalid or has expired", code="invalid_reset_token")
    row.used_at = datetime.now(UTC)
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    audit.record(db, action="auth.password_reset", entity_type="user", entity_id=user.id, actor_user_id=user.id,
                 ip_address=_client_ip(request))
    db.commit()


@users_router.post("/users/{user_id}/password-reset", response_model=ResetIssued, status_code=201)
def issue_password_reset(user_id: uuid.UUID, ctx: TenantContext = Depends(require(P.USERS_MANAGE))):
    """One-time reset token for a member (delivered by the administrator; shown once)."""
    m = _membership(ctx, user_id)
    if m.user.email.endswith("@service.invalid"):
        raise BusinessRuleError("Service accounts have no password", code="service_account")
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_ttl_minutes)
    ctx.db.add(PasswordResetToken(user_id=user_id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                  created_by=ctx.user_id, expires_at=expires))
    ctx.audit(action="user.password_reset_issued", entity_type="user", entity_id=user_id,
              changes={"expires_at": expires.isoformat()})
    ctx.db.commit()
    return ResetIssued(reset_token=raw, expires_at=expires)
