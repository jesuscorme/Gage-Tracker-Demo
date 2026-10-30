import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.modules.competency import service
from app.modules.competency.models import (
    ACTIVITIES,
    PROFILE_TYPES,
    RECORD_RESULTS,
    RECORD_TYPES,
    Authorization,
    Competency,
    CompetencyRecord,
    PersonnelProfile,
)
from app.modules.documents import service as documents
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.models import OrganizationMembership, User
from app.modules.identity.permissions import P

router = APIRouter(prefix="/competency", tags=["competency"])
documents.register("competency_record", P.COMPETENCY_READ, P.COMPETENCY_MANAGE,
                   lambda ctx, i: service.get_record(ctx, i))

Activity = Literal[ACTIVITIES]  # type: ignore[valid-type]
ProfileType = Literal[PROFILE_TYPES]  # type: ignore[valid-type]


class ProfileIn(BaseModel):
    employee_number: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    profile_types: list[ProfileType] = []
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class PersonOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    has_profile: bool
    employee_number: str | None = None
    job_title: str | None = None
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    profile_types: list[str] = []
    is_active: bool = True
    notes: str | None = None
    current_authorizations: list[str] = []


class CompetencyIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    validity_months: int | None = Field(default=None, ge=1, le=120)


class CompetencyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    validity_months: int | None = Field(default=None, ge=1, le=120)
    is_active: bool | None = None


class CompetencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    validity_months: int | None
    is_active: bool


class RecordIn(BaseModel):
    user_id: uuid.UUID
    competency_id: uuid.UUID
    record_type: Literal[RECORD_TYPES]  # type: ignore[valid-type]
    title: str = Field(min_length=2, max_length=200)
    provider: str | None = Field(default=None, max_length=200)
    completed_on: date
    valid_until: date | None = None
    result: Literal[RECORD_RESULTS]  # type: ignore[valid-type]
    score: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    competency_id: uuid.UUID
    record_type: str
    title: str
    provider: str | None
    completed_on: date
    valid_until: date | None
    result: str
    score: str | None
    notes: str | None
    recorded_at: datetime


class AuthorizationIn(BaseModel):
    user_id: uuid.UUID
    activity: Activity
    gage_type_id: uuid.UUID | None = None
    plant_id: uuid.UUID | None = None
    valid_from: date
    valid_until: date | None = None
    basis: str | None = Field(default=None, max_length=500)
    competency_record_id: uuid.UUID | None = None


class AuthorizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    activity: str
    gage_type_id: uuid.UUID | None
    plant_id: uuid.UUID | None
    valid_from: date
    valid_until: date | None
    basis: str | None
    competency_record_id: uuid.UUID | None
    granted_by: uuid.UUID
    granted_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None
    state: str = "CURRENT"


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _auth_out(ctx: TenantContext, rows: list[Authorization]) -> list[AuthorizationOut]:
    ids = {a.user_id for a in rows}
    names = {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))} if ids else {}
    today, window = ctx.today(), ctx.organization.due_soon_days
    return [AuthorizationOut.model_validate(a).model_copy(update={
        "user_name": names.get(a.user_id), "state": service.authorization_state(a, today, window)}) for a in rows]


# ---------------------------------------------------------------- people


@router.get("/people", response_model=list[PersonOut])
def list_people(ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    """Every active member, with their profile (if any) and current authorizations."""
    rows = ctx.db.execute(
        select(User, PersonnelProfile)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .outerjoin(PersonnelProfile, (PersonnelProfile.user_id == User.id)
                   & (PersonnelProfile.organization_id == ctx.organization_id))
        .where(OrganizationMembership.organization_id == ctx.organization_id,
               OrganizationMembership.is_active.is_(True))
        .order_by(User.full_name)
    ).all()
    auths: dict[uuid.UUID, set[str]] = {}
    for a in service.list_authorizations(ctx, None, include_revoked=False):
        if service.authorization_state(a, ctx.today(), 0) in ("CURRENT", "EXPIRING"):
            auths.setdefault(a.user_id, set()).add(a.activity)
    out = []
    for u, p in rows:
        base = dict(user_id=u.id, full_name=u.full_name, email=u.email, has_profile=p is not None,
                    current_authorizations=sorted(auths.get(u.id, set())))
        if p:
            base.update(employee_number=p.employee_number, job_title=p.job_title, plant_id=p.plant_id,
                        department_id=p.department_id, profile_types=p.profile_types, is_active=p.is_active,
                        notes=p.notes)
        out.append(PersonOut(**base))
    return out


@router.put("/people/{user_id}", response_model=PersonOut)
def save_profile(user_id: uuid.UUID, body: ProfileIn, ctx: TenantContext = Depends(require(P.COMPETENCY_MANAGE))):
    p = service.upsert_profile(ctx, user_id, body.model_dump())
    u = ctx.db.get(User, user_id)
    return PersonOut(user_id=u.id, full_name=u.full_name, email=u.email, has_profile=True,
                     **{k: getattr(p, k) for k in ("employee_number", "job_title", "plant_id", "department_id",
                                                   "profile_types", "is_active", "notes")})


# ---------------------------------------------------------------- catalogue & records


@router.get("/competencies", response_model=list[CompetencyOut])
def list_competencies(ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    return list(ctx.db.scalars(select(Competency).where(Competency.organization_id == ctx.organization_id)
                               .order_by(Competency.code)))


@router.post("/competencies", response_model=CompetencyOut, status_code=201)
def create_competency(body: CompetencyIn, ctx: TenantContext = Depends(require(P.COMPETENCY_MANAGE))):
    return service.create_competency(ctx, body.model_dump())


@router.patch("/competencies/{competency_id}", response_model=CompetencyOut)
def update_competency(competency_id: uuid.UUID, body: CompetencyUpdate,
                      ctx: TenantContext = Depends(require(P.COMPETENCY_MANAGE))):
    data = body.model_dump(exclude_unset=True)
    data = {k: v for k, v in data.items() if not (k in ("name", "is_active") and v is None)}
    return service.update_competency(ctx, competency_id, data)


@router.get("/records", response_model=list[RecordOut])
def list_records(user_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    stmt = select(CompetencyRecord).where(CompetencyRecord.organization_id == ctx.organization_id)
    if user_id:
        stmt = stmt.where(CompetencyRecord.user_id == user_id)
    return list(ctx.db.scalars(stmt.order_by(CompetencyRecord.completed_on.desc())))


@router.post("/records", response_model=RecordOut, status_code=201)
def add_record(body: RecordIn, ctx: TenantContext = Depends(require(P.COMPETENCY_MANAGE))):
    return service.add_record(ctx, body.model_dump())


@router.get("/matrix")
def competency_matrix(ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    return service.matrix(ctx)


# ---------------------------------------------------------------- authorizations


@router.get("/authorizations", response_model=list[AuthorizationOut])
def list_authorizations(user_id: uuid.UUID | None = None, include_revoked: bool = False,
                        ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    return _auth_out(ctx, service.list_authorizations(ctx, user_id, include_revoked))


@router.post("/authorizations", response_model=AuthorizationOut, status_code=201)
def grant_authorization(body: AuthorizationIn, ctx: TenantContext = Depends(require(P.COMPETENCY_AUTHORIZE))):
    return _auth_out(ctx, [service.grant(ctx, body.model_dump())])[0]


@router.post("/authorizations/{authorization_id}/revoke", response_model=AuthorizationOut)
def revoke_authorization(authorization_id: uuid.UUID, body: RevokeIn,
                         ctx: TenantContext = Depends(require(P.COMPETENCY_AUTHORIZE))):
    return _auth_out(ctx, [service.revoke(ctx, authorization_id, body.reason.strip())])[0]


@router.get("/authorized-users")
def authorized_users(activity: Activity, gage_type_id: uuid.UUID | None = None, plant_id: uuid.UUID | None = None,
                     ctx: TenantContext = Depends(require(P.COMPETENCY_READ))):
    """People with a current authorization (for assignment pickers)."""
    return [{"id": str(u.id), "full_name": u.full_name}
            for u in service.authorized_users(ctx, activity, gage_type_id, plant_id)]
