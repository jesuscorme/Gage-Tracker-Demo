import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import select

from app.modules.calibration import service
from app.modules.calibration.models import (
    ACTIVITY_TYPES,
    RESULTS,
    STATUSES,
    CalibrationActivity,
    CalibrationCertificate,
    CalibrationPoint,
    CalibrationStandardUsage,
    CalibrationStatusHistory,
)
from app.modules.documents import service as documents
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.models import User
from app.modules.identity.permissions import P
from app.modules.standards.models import Standard

router = APIRouter(tags=["calibration"])
documents.register("calibration", P.CALIBRATION_READ, P.CALIBRATION_EXECUTE, lambda ctx, i: service.get_activity(ctx, i))

ActivityType = Literal[ACTIVITY_TYPES]  # type: ignore[valid-type]
Status = Literal[STATUSES]  # type: ignore[valid-type]
Result = Literal[RESULTS]  # type: ignore[valid-type]


def _dec(v):
    return None if v is None else format(v.normalize(), "f")


class ActivityCreate(BaseModel):
    gage_id: uuid.UUID
    activity_type: ActivityType
    planned_date: date
    technician_id: uuid.UUID | None = None
    provider_name: str | None = Field(default=None, max_length=200)
    method: str | None = Field(default=None, max_length=300)


class ActivityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_date: date | None = None
    scheduled_date: date | None = None
    provider_name: str | None = Field(default=None, max_length=200)
    provider_accreditation: str | None = Field(default=None, max_length=120)
    technician_id: uuid.UUID | None = None
    method: str | None = Field(default=None, max_length=300)
    performed_date: date | None = None
    environment_temperature: Decimal | None = Field(default=None, ge=-50, le=200, decimal_places=2)
    environment_humidity: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    environment_notes: str | None = Field(default=None, max_length=300)
    uncertainty: str | None = Field(default=None, max_length=200)
    adjusted: bool | None = None
    declared_result: Result | None = None
    observations: str | None = Field(default=None, max_length=4000)


class ScheduleIn(BaseModel):
    scheduled_date: date
    technician_id: uuid.UUID | None = None
    provider_name: str | None = Field(default=None, max_length=200)
    provider_accreditation: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=1000)


class CommentIn(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    accept: bool
    comments: str | None = Field(default=None, max_length=2000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class PointIn(BaseModel):
    phase: Literal["AS_FOUND", "AS_LEFT"]
    description: str | None = Field(default=None, max_length=200)
    nominal: Decimal = Field(max_digits=18, decimal_places=6)
    lower_limit: Decimal = Field(max_digits=18, decimal_places=6)
    upper_limit: Decimal = Field(max_digits=18, decimal_places=6)
    measured: Decimal = Field(max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, max_length=20)
    uncertainty: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    supersedes_id: uuid.UUID | None = None
    correction_reason: str | None = Field(default=None, max_length=500)


class StandardUseIn(BaseModel):
    standard_id: uuid.UUID
    exception_reason: str | None = Field(default=None, min_length=5, max_length=500)


class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    phase: str
    sequence: int
    description: str | None
    nominal: Decimal
    lower_limit: Decimal
    upper_limit: Decimal
    measured: Decimal
    unit: str | None
    uncertainty: Decimal | None
    in_tolerance: bool
    superseded: bool
    supersedes_id: uuid.UUID | None
    correction_reason: str | None
    recorded_by: uuid.UUID
    recorded_at: datetime

    @field_serializer("nominal", "lower_limit", "upper_limit", "measured", "uncertainty")
    def _d(self, v):
        return _dec(v)


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    certificate_number: str
    issuer: str
    issue_date: date
    attachment_id: uuid.UUID
    status: str
    superseded_reason: str | None
    uploaded_at: datetime


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    standard_id: uuid.UUID
    standard_code: str | None = None
    standard_description: str | None = None
    used_on: date
    standard_status: str
    certificate_id: uuid.UUID | None
    valid_until: date | None
    is_exception: bool
    exception_reason: str | None


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_status: str | None
    to_status: str
    comment: str | None
    changed_by: uuid.UUID
    changed_by_name: str | None = None
    changed_at: datetime


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    calibration_code: str
    activity_type: str
    status: str
    gage_id: uuid.UUID
    gage_code: str = ""
    gage_description: str = ""
    plant_id: uuid.UUID
    planned_date: date
    scheduled_date: date | None
    provider_name: str | None
    provider_accreditation: str | None
    technician_id: uuid.UUID | None
    technician_name: str | None = None
    started_at: datetime | None
    performed_date: date | None
    method: str | None
    environment_temperature: Decimal | None
    environment_humidity: Decimal | None
    environment_notes: str | None
    uncertainty: str | None
    adjusted: bool
    declared_result: str | None
    observations: str | None
    result: str | None
    as_found_in_tolerance: bool | None
    as_left_in_tolerance: bool | None
    submitted_at: datetime | None
    reviewer_id: uuid.UUID | None
    reviewer_name: str | None = None
    reviewed_at: datetime | None
    review_comments: str | None
    approver_id: uuid.UUID | None
    approver_name: str | None = None
    approved_at: datetime | None
    released_at: datetime | None
    released_by_name: str | None = None
    due_date: date | None
    cancel_reason: str | None
    created_at: datetime

    @field_serializer("environment_temperature", "environment_humidity")
    def _d(self, v):
        return _dec(v)


class ActivityDetail(ActivityOut):
    points: list[PointOut]
    certificates: list[CertificateOut]
    standards: list[UsageOut]
    history: list[HistoryOut]
    missing_requirements: list[str]
    requirements: dict
    computed_result: str | None


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int


class SettingIn(BaseModel):
    plant_id: uuid.UUID | None = None
    activity_type: ActivityType
    enabled: bool
    require_certificate: bool
    require_standard: bool
    require_as_found: bool
    require_environment: bool


def _names(ctx: TenantContext, ids) -> dict:
    ids = {i for i in ids if i}
    return {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))} if ids else {}


def to_out(ctx: TenantContext, rows: list[CalibrationActivity]) -> list[ActivityOut]:
    names = _names(ctx, [x for a in rows for x in (a.technician_id, a.reviewer_id, a.approver_id, a.released_by)])
    return [ActivityOut.model_validate(a).model_copy(update={
        "gage_code": a.gage.gage_code, "gage_description": a.gage.description,
        "technician_name": names.get(a.technician_id), "reviewer_name": names.get(a.reviewer_id),
        "approver_name": names.get(a.approver_id), "released_by_name": names.get(a.released_by),
    }) for a in rows]


def detail(ctx: TenantContext, a: CalibrationActivity) -> ActivityDetail:
    ctx.db.refresh(a)
    base = to_out(ctx, [a])[0]
    points = list(ctx.db.scalars(select(CalibrationPoint).where(CalibrationPoint.calibration_id == a.id)
                                 .order_by(CalibrationPoint.phase, CalibrationPoint.sequence, CalibrationPoint.recorded_at)))
    certs = list(ctx.db.scalars(select(CalibrationCertificate).where(CalibrationCertificate.calibration_id == a.id)
                                .order_by(CalibrationCertificate.uploaded_at.desc())))
    usages = ctx.db.execute(select(CalibrationStandardUsage, Standard)
                            .join(Standard, Standard.id == CalibrationStandardUsage.standard_id)
                            .where(CalibrationStandardUsage.calibration_id == a.id)).unique().all()
    hist = list(ctx.db.scalars(select(CalibrationStatusHistory).where(CalibrationStatusHistory.calibration_id == a.id)
                               .order_by(CalibrationStatusHistory.changed_at.desc())))
    names = _names(ctx, [h.changed_by for h in hist])
    current = [p for p in points if not p.superseded]
    in_progress = a.status == "IN_PROGRESS"
    return ActivityDetail(
        **base.model_dump(),
        points=points,
        certificates=certs,
        standards=[UsageOut.model_validate(u).model_copy(update={"standard_code": s.standard_code,
                                                                 "standard_description": s.description})
                   for u, s in usages],
        history=[HistoryOut.model_validate(h).model_copy(update={"changed_by_name": names.get(h.changed_by)})
                 for h in hist],
        missing_requirements=service.missing_requirements(ctx, a) if in_progress else [],
        requirements=service.effective_settings(ctx, a.plant_id)[a.activity_type],
        computed_result=service.compute_outcome(a, current)[0] if in_progress else a.result,
    )


# ---------------------------------------------------------------- settings


@router.get("/calibration-settings")
def get_settings(plant_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require(P.CALIBRATION_READ))):
    return service.effective_settings(ctx, plant_id)


@router.put("/calibration-settings")
def put_settings(body: SettingIn, ctx: TenantContext = Depends(require(P.CALIBRATION_SETTINGS))):
    values = body.model_dump(exclude={"plant_id", "activity_type"})
    return service.save_setting(ctx, body.plant_id, body.activity_type, values)


# ---------------------------------------------------------------- activities


@router.get("/calibrations/overview")
def calibration_overview(ctx: TenantContext = Depends(require(P.CALIBRATION_READ, P.GAGES_READ))):
    return service.overview(ctx)


@router.get("/calibrations/calendar")
def calibration_calendar(start: date, end: date, ctx: TenantContext = Depends(require(P.CALIBRATION_READ))):
    return service.calendar(ctx, start, end)


@router.get("/calibrations", response_model=ActivityPage)
def list_calibrations(
    gage_id: uuid.UUID | None = None,
    status: list[Status] | None = Query(None),
    activity_type: ActivityType | None = None,
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require(P.CALIBRATION_READ)),
):
    rows, total = service.list_activities(ctx, gage_id=gage_id, status=status, activity_type=activity_type, q=q,
                                          page=page, page_size=page_size)
    return ActivityPage(items=to_out(ctx, rows), total=total)


@router.post("/calibrations", response_model=ActivityDetail, status_code=201)
def create_calibration(body: ActivityCreate, ctx: TenantContext = Depends(require(P.CALIBRATION_MANAGE))):
    return detail(ctx, service.create(ctx, body.model_dump()))


@router.get("/calibrations/{activity_id}", response_model=ActivityDetail)
def get_calibration(activity_id: uuid.UUID, ctx: TenantContext = Depends(require(P.CALIBRATION_READ))):
    return detail(ctx, service.get_activity(ctx, activity_id))


@router.patch("/calibrations/{activity_id}", response_model=ActivityDetail)
def update_calibration(activity_id: uuid.UUID, body: ActivityUpdate,
                       ctx: TenantContext = Depends(require(P.CALIBRATION_READ))):
    return detail(ctx, service.update(ctx, activity_id, body.model_dump(exclude_unset=True)))


@router.post("/calibrations/{activity_id}/request", response_model=ActivityDetail)
def request_calibration(activity_id: uuid.UUID, body: CommentIn,
                        ctx: TenantContext = Depends(require(P.CALIBRATION_MANAGE))):
    return detail(ctx, service.request(ctx, activity_id, body.comment))


@router.post("/calibrations/{activity_id}/schedule", response_model=ActivityDetail)
def schedule_calibration(activity_id: uuid.UUID, body: ScheduleIn,
                         ctx: TenantContext = Depends(require(P.CALIBRATION_MANAGE))):
    return detail(ctx, service.schedule(ctx, activity_id, body.model_dump()))


@router.post("/calibrations/{activity_id}/start", response_model=ActivityDetail)
def start_calibration(activity_id: uuid.UUID, ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE))):
    return detail(ctx, service.start(ctx, activity_id))


@router.post("/calibrations/{activity_id}/points", response_model=ActivityDetail, status_code=201)
def add_point(activity_id: uuid.UUID, body: PointIn, ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE))):
    service.add_point(ctx, activity_id, body.model_dump())
    return detail(ctx, service.get_activity(ctx, activity_id))


@router.post("/calibrations/{activity_id}/standards", response_model=ActivityDetail, status_code=201)
def add_standard(activity_id: uuid.UUID, body: StandardUseIn,
                 ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE, P.STANDARDS_READ))):
    service.add_standard(ctx, activity_id, body.standard_id, body.exception_reason)
    return detail(ctx, service.get_activity(ctx, activity_id))


@router.post("/calibrations/{activity_id}/standards/{usage_id}/remove", response_model=ActivityDetail)
def remove_standard(activity_id: uuid.UUID, usage_id: uuid.UUID, body: ReasonIn,
                    ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE))):
    service.remove_standard(ctx, activity_id, usage_id, body.reason)
    return detail(ctx, service.get_activity(ctx, activity_id))


@router.post("/calibrations/{activity_id}/certificates", response_model=ActivityDetail, status_code=201)
async def add_certificate(
    activity_id: uuid.UUID,
    certificate_number: str = Form(..., min_length=1, max_length=80),
    issuer: str = Form(..., min_length=2, max_length=200),
    issue_date: date = Form(...),
    replace_reason: str | None = Form(None, max_length=500),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE)),
):
    meta = {"certificate_number": certificate_number, "issuer": issuer, "issue_date": issue_date}
    service.add_certificate(ctx, activity_id, meta, file.filename or "certificate.pdf", await file.read(), replace_reason)
    return detail(ctx, service.get_activity(ctx, activity_id))


@router.post("/calibrations/{activity_id}/submit", response_model=ActivityDetail)
def submit_calibration(activity_id: uuid.UUID, body: CommentIn,
                       ctx: TenantContext = Depends(require(P.CALIBRATION_EXECUTE))):
    return detail(ctx, service.submit(ctx, activity_id, body.comment))


@router.post("/calibrations/{activity_id}/review", response_model=ActivityDetail)
def review_calibration(activity_id: uuid.UUID, body: DecisionIn,
                       ctx: TenantContext = Depends(require(P.CALIBRATION_REVIEW))):
    return detail(ctx, service.review(ctx, activity_id, body.accept, body.comments))


@router.post("/calibrations/{activity_id}/approve", response_model=ActivityDetail)
def approve_calibration(activity_id: uuid.UUID, body: DecisionIn,
                        ctx: TenantContext = Depends(require(P.CALIBRATION_APPROVE))):
    return detail(ctx, service.approve(ctx, activity_id, body.accept, body.comments))


@router.post("/calibrations/{activity_id}/release", response_model=ActivityDetail)
def release_calibration(activity_id: uuid.UUID, body: CommentIn,
                        ctx: TenantContext = Depends(require(P.CALIBRATION_RELEASE))):
    return detail(ctx, service.release(ctx, activity_id, body.comment))


@router.post("/calibrations/{activity_id}/cancel", response_model=ActivityDetail)
def cancel_calibration(activity_id: uuid.UUID, body: ReasonIn,
                       ctx: TenantContext = Depends(require(P.CALIBRATION_MANAGE))):
    return detail(ctx, service.cancel(ctx, activity_id, body.reason.strip()))


@router.get("/standards/{standard_id}/usages")
def standard_usages(standard_id: uuid.UUID, ctx: TenantContext = Depends(require(P.STANDARDS_READ, P.CALIBRATION_READ))):
    """Which activities used the standard, its condition and certificate on that date."""
    return [
        {"usage_id": str(u.id), "calibration_id": str(a.id), "calibration_code": a.calibration_code,
         "activity_type": a.activity_type, "activity_status": a.status, "gage_code": a.gage.gage_code,
         "used_on": u.used_on.isoformat(), "standard_status": u.standard_status,
         "certificate_id": str(u.certificate_id) if u.certificate_id else None,
         "valid_until": u.valid_until.isoformat() if u.valid_until else None,
         "is_exception": u.is_exception, "exception_reason": u.exception_reason}
        for u, a in service.standard_usages(ctx, standard_id)
    ]


@router.get("/gages/{gage_id}/calibration-summary")
def gage_calibration_summary(gage_id: uuid.UUID, ctx: TenantContext = Depends(require(P.CALIBRATION_READ))):
    rows, _ = service.list_activities(ctx, gage_id=gage_id, page_size=200)
    certs = list(ctx.db.scalars(select(CalibrationCertificate).where(
        CalibrationCertificate.gage_id == gage_id, CalibrationCertificate.organization_id == ctx.organization_id)
        .order_by(CalibrationCertificate.uploaded_at.desc())))
    return {"activities": to_out(ctx, rows), "certificates": [CertificateOut.model_validate(c) for c in certs]}

