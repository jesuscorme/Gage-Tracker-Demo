"""Competency Management: profiles, competency records and activity authorizations.

``ensure_authorized`` is the single check used by Calibration and Laboratory before a
person executes, reviews or approves a restricted activity.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.audit import service as audit
from app.modules.competency.models import Authorization, Competency, CompetencyRecord, PersonnelProfile
from app.modules.gages.service import ensure_active_member, get_gage_type
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import User
from app.modules.organizations.models import Department
from app.modules.organizations.router import get_plant


# ---------------------------------------------------------------- authorizations


def _active_authorizations(ctx: TenantContext, user_id: uuid.UUID, activity: str, on: date):
    return select(Authorization).where(
        Authorization.organization_id == ctx.organization_id,
        Authorization.user_id == user_id,
        Authorization.activity == activity,
        Authorization.revoked_at.is_(None),
        Authorization.valid_from <= on,
        or_(Authorization.valid_until.is_(None), Authorization.valid_until >= on),
    )


def find_authorization(ctx: TenantContext, user_id: uuid.UUID, activity: str, on: date,
                       gage_type_id: uuid.UUID | None = None, plant_id: uuid.UUID | None = None) -> Authorization | None:
    stmt = _active_authorizations(ctx, user_id, activity, on)
    stmt = stmt.where(or_(Authorization.gage_type_id.is_(None), Authorization.gage_type_id == gage_type_id))
    stmt = stmt.where(or_(Authorization.plant_id.is_(None), Authorization.plant_id == plant_id))
    return ctx.db.scalars(stmt).first()


def ensure_authorized(ctx: TenantContext, user_id: uuid.UUID, activity: str, *, on: date | None = None,
                      gage_type_id: uuid.UUID | None = None, plant_id: uuid.UUID | None = None) -> Authorization:
    auth = find_authorization(ctx, user_id, activity, on or ctx.today(), gage_type_id, plant_id)
    if auth is None:
        name = ctx.db.scalar(select(User.full_name).where(User.id == user_id))
        raise BusinessRuleError(
            f"{name or 'The user'} has no current authorization for {activity}",
            code="not_authorized",
            details={"user_id": str(user_id), "activity": activity,
                     "gage_type_id": str(gage_type_id) if gage_type_id else None,
                     "plant_id": str(plant_id) if plant_id else None},
        )
    return auth


def authorized_users(ctx: TenantContext, activity: str, gage_type_id: uuid.UUID | None,
                     plant_id: uuid.UUID | None) -> list[User]:
    on = ctx.today()
    stmt = (
        select(User).join(Authorization, Authorization.user_id == User.id)
        .where(Authorization.organization_id == ctx.organization_id, Authorization.activity == activity,
               Authorization.revoked_at.is_(None), Authorization.valid_from <= on,
               or_(Authorization.valid_until.is_(None), Authorization.valid_until >= on),
               or_(Authorization.gage_type_id.is_(None), Authorization.gage_type_id == gage_type_id),
               or_(Authorization.plant_id.is_(None), Authorization.plant_id == plant_id))
        .distinct().order_by(User.full_name)
    )
    return list(ctx.db.scalars(stmt))


def grant(ctx: TenantContext, data: dict) -> Authorization:
    ensure_active_member(ctx, data["user_id"])
    if data.get("gage_type_id"):
        get_gage_type(ctx, data["gage_type_id"])
    if data.get("plant_id"):
        get_plant(ctx, data["plant_id"])
    if data.get("valid_until") and data["valid_until"] < data["valid_from"]:
        raise BusinessRuleError("valid_until must be on or after valid_from", code="invalid_dates")
    if data.get("valid_until") and data["valid_until"] < ctx.today():
        raise BusinessRuleError("The authorization would already be expired", code="invalid_dates")
    if data.get("competency_record_id"):
        rec = ctx.db.get(CompetencyRecord, data["competency_record_id"])
        if rec is None or rec.organization_id != ctx.organization_id or rec.user_id != data["user_id"]:
            raise NotFoundError("Competency record not found")
        if rec.result != "PASSED":
            raise BusinessRuleError("The supporting record is not PASSED", code="record_not_passed")
    auth = Authorization(organization_id=ctx.organization_id, granted_by=ctx.user_id, **data)
    ctx.db.add(auth)
    ctx.db.flush()
    ctx.audit(action="authorization.granted", entity_type="user", entity_id=data["user_id"],
              changes={k: audit.plain(v) for k, v in data.items()} | {"authorization_id": str(auth.id)})
    ctx.db.commit()
    return auth


def revoke(ctx: TenantContext, authorization_id: uuid.UUID, reason: str) -> Authorization:
    auth = ctx.db.scalar(select(Authorization).where(Authorization.id == authorization_id,
                                                     Authorization.organization_id == ctx.organization_id))
    if auth is None:
        raise NotFoundError("Authorization not found")
    if auth.revoked_at:
        raise ConflictError("Authorization already revoked", code="already_revoked")
    auth.revoked_at = datetime.now(UTC)
    auth.revoked_by = ctx.user_id
    auth.revoke_reason = reason
    ctx.audit(action="authorization.revoked", entity_type="user", entity_id=auth.user_id, reason=reason,
              changes={"authorization_id": str(auth.id), "activity": auth.activity})
    ctx.db.commit()
    return auth


def list_authorizations(ctx: TenantContext, user_id: uuid.UUID | None, include_revoked: bool) -> list[Authorization]:
    stmt = select(Authorization).where(Authorization.organization_id == ctx.organization_id)
    if user_id:
        stmt = stmt.where(Authorization.user_id == user_id)
    if not include_revoked:
        stmt = stmt.where(Authorization.revoked_at.is_(None))
    return list(ctx.db.scalars(stmt.order_by(Authorization.granted_at.desc())))


def authorization_state(a: Authorization, on: date, window: int) -> str:
    if a.revoked_at:
        return "REVOKED"
    if a.valid_from > on:
        return "PENDING"
    if a.valid_until and a.valid_until < on:
        return "EXPIRED"
    if a.valid_until and a.valid_until <= on + timedelta(days=window):
        return "EXPIRING"
    return "CURRENT"


# ---------------------------------------------------------------- profiles, catalogue, records


def upsert_profile(ctx: TenantContext, user_id: uuid.UUID, data: dict) -> PersonnelProfile:
    ensure_active_member(ctx, user_id)
    if data.get("plant_id"):
        get_plant(ctx, data["plant_id"])
    if data.get("department_id"):
        dept = ctx.db.get(Department, data["department_id"])
        if dept is None or dept.organization_id != ctx.organization_id:
            raise NotFoundError("Department not found")
        if data.get("plant_id") and dept.plant_id != data["plant_id"]:
            raise BusinessRuleError("Department does not belong to the selected plant", code="department_plant_mismatch")
    prof = ctx.db.scalar(select(PersonnelProfile).where(PersonnelProfile.organization_id == ctx.organization_id,
                                                        PersonnelProfile.user_id == user_id))
    fields = ["employee_number", "job_title", "plant_id", "department_id", "profile_types", "is_active", "notes"]
    before = audit.snapshot(prof, fields) if prof else {}
    if prof is None:
        prof = PersonnelProfile(organization_id=ctx.organization_id, user_id=user_id)
        ctx.db.add(prof)
    for k, v in data.items():
        setattr(prof, k, v)
    ctx.db.flush()
    ctx.audit(action="personnel_profile.saved", entity_type="user", entity_id=user_id,
              changes=audit.diff(before, audit.snapshot(prof, fields)))
    ctx.db.commit()
    return prof


def get_competency(ctx: TenantContext, competency_id: uuid.UUID) -> Competency:
    c = ctx.db.scalar(select(Competency).where(Competency.id == competency_id,
                                               Competency.organization_id == ctx.organization_id))
    if c is None:
        raise NotFoundError("Competency not found")
    return c


def create_competency(ctx: TenantContext, data: dict) -> Competency:
    data["code"] = data["code"].strip().upper()
    if ctx.db.scalar(select(Competency.id).where(Competency.organization_id == ctx.organization_id,
                                                 Competency.code == data["code"])):
        raise ConflictError("Competency code already exists", code="duplicate_competency")
    c = Competency(organization_id=ctx.organization_id, **data)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.audit(action="competency.created", entity_type="competency", entity_id=c.id,
              changes={k: audit.plain(v) for k, v in data.items()})
    ctx.db.commit()
    return c


def update_competency(ctx: TenantContext, competency_id: uuid.UUID, data: dict) -> Competency:
    c = get_competency(ctx, competency_id)
    before = audit.snapshot(c, list(data))
    for k, v in data.items():
        setattr(c, k, v)
    ctx.audit(action="competency.updated", entity_type="competency", entity_id=c.id,
              changes=audit.diff(before, audit.snapshot(c, list(data))))
    ctx.db.commit()
    return c


def get_record(ctx: TenantContext, record_id: uuid.UUID) -> CompetencyRecord:
    r = ctx.db.scalar(select(CompetencyRecord).where(CompetencyRecord.id == record_id,
                                                     CompetencyRecord.organization_id == ctx.organization_id))
    if r is None:
        raise NotFoundError("Competency record not found")
    return r


def add_record(ctx: TenantContext, data: dict) -> CompetencyRecord:
    ensure_active_member(ctx, data["user_id"])
    comp = get_competency(ctx, data["competency_id"])
    if data["completed_on"] > ctx.today():
        raise BusinessRuleError("completed_on cannot be in the future", code="future_date")
    if data.get("valid_until") is None and comp.validity_months and data["result"] == "PASSED":
        data["valid_until"] = data["completed_on"] + timedelta(days=round(comp.validity_months * 30.44))
    if data.get("valid_until") and data["valid_until"] < data["completed_on"]:
        raise BusinessRuleError("valid_until must be on or after completed_on", code="invalid_dates")
    rec = CompetencyRecord(organization_id=ctx.organization_id, recorded_by=ctx.user_id, **data)
    ctx.db.add(rec)
    ctx.db.flush()
    ctx.audit(action="competency_record.added", entity_type="user", entity_id=data["user_id"],
              changes={k: audit.plain(v) for k, v in data.items()} | {"record_id": str(rec.id)})
    ctx.db.commit()
    return rec


def matrix(ctx: TenantContext) -> dict:
    """Users with a profile x active competencies -> state of the best current record."""
    today, window = ctx.today(), ctx.organization.due_soon_days
    comps = list(ctx.db.scalars(select(Competency).where(Competency.organization_id == ctx.organization_id,
                                                         Competency.is_active.is_(True)).order_by(Competency.code)))
    profiles = list(ctx.db.execute(
        select(PersonnelProfile, User).join(User, User.id == PersonnelProfile.user_id)
        .where(PersonnelProfile.organization_id == ctx.organization_id, PersonnelProfile.is_active.is_(True))
        .order_by(User.full_name)
    ))
    records = list(ctx.db.scalars(select(CompetencyRecord).where(
        CompetencyRecord.organization_id == ctx.organization_id)))
    best: dict[tuple, str] = {}
    rank = {"CURRENT": 4, "EXPIRING": 3, "EXPIRED": 2, "FAILED": 1}
    for r in records:
        if r.result == "FAILED":
            state = "FAILED"
        elif r.valid_until and r.valid_until < today:
            state = "EXPIRED"
        elif r.valid_until and r.valid_until <= today + timedelta(days=window):
            state = "EXPIRING"
        else:
            state = "CURRENT"
        key = (r.user_id, r.competency_id)
        if rank[state] > rank.get(best.get(key, ""), 0):
            best[key] = state
    return {
        "competencies": [{"id": str(c.id), "code": c.code, "name": c.name} for c in comps],
        "rows": [
            {"user_id": str(u.id), "full_name": u.full_name, "job_title": p.job_title,
             "profile_types": p.profile_types,
             "cells": {str(c.id): best.get((u.id, c.id), "NONE") for c in comps}}
            for p, u in profiles
        ],
    }
