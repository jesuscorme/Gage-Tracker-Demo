import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.modules.documents import service as documents
from app.modules.gages.schemas import Ref, UserRef
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.standards import service
from app.modules.standards.models import CATEGORIES, Standard

router = APIRouter(prefix="/standards", tags=["standards"])
documents.register("standard", P.STANDARDS_READ, P.STANDARDS_MANAGE, lambda ctx, i: service.get_standard(ctx, i))

Category = Literal[CATEGORIES]  # type: ignore[valid-type]


class _StandardFields(BaseModel):
    description: str | None = Field(default=None, min_length=2, max_length=300)
    category: Category | None = None
    subtype: str | None = Field(default=None, max_length=120)
    plant_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    range_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    range_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, max_length=20)
    resolution: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    accuracy: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    custodian_user_id: uuid.UUID | None = None
    calibration_frequency_days: int | None = Field(default=None, ge=1, le=3650)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _range(self):
        if self.range_min is not None and self.range_max is not None and self.range_min > self.range_max:
            raise ValueError("range_min must be less than or equal to range_max")
        return self


class StandardCreate(_StandardFields):
    standard_code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    description: str = Field(min_length=2, max_length=300)
    category: Category
    plant_id: uuid.UUID
    calibration_frequency_days: int = Field(ge=1, le=3650)


class StandardUpdate(_StandardFields):
    model_config = ConfigDict(extra="forbid")


class StandardOut(BaseModel):
    id: uuid.UUID
    standard_code: str
    description: str
    category: str
    subtype: str | None
    plant: Ref
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    range_min: Decimal | None
    range_max: Decimal | None
    unit: str | None
    resolution: Decimal | None
    accuracy: str | None
    location: str | None
    custodian: UserRef | None
    calibration_frequency_days: int
    last_calibration_date: date | None
    valid_until: date | None
    days_to_expiry: int | None
    current_certificate_id: uuid.UUID | None
    control_status: str
    status: service.StandardStatus
    usable: bool
    notes: str | None
    updated_at: datetime

    @field_serializer("range_min", "range_max", "resolution")
    def _dec(self, v: Decimal | None):
        return None if v is None else format(v.normalize(), "f")


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    certificate_number: str
    issuer: str
    accreditation: str | None
    calibration_date: date
    issue_date: date
    valid_until: date
    uncertainty: str | None
    traceability: str | None
    attachment_id: uuid.UUID
    status: str
    created_at: datetime


class TransitionIn(BaseModel):
    target: Literal["ACTIVE", "RESTRICTED", "INACTIVE"]
    reason: str = Field(min_length=3, max_length=1000)


def to_out(ctx: TenantContext, s: Standard) -> StandardOut:
    st = service.status(ctx, s)
    return StandardOut(
        **{k: getattr(s, k) for k in (
            "id", "standard_code", "description", "category", "subtype", "manufacturer", "model", "serial_number",
            "range_min", "range_max", "unit", "resolution", "accuracy", "location", "calibration_frequency_days",
            "last_calibration_date", "valid_until", "current_certificate_id", "control_status", "notes", "updated_at")},
        plant=Ref.model_validate(s.plant), custodian=UserRef.model_validate(s.custodian) if s.custodian else None,
        days_to_expiry=(s.valid_until - ctx.today()).days if s.valid_until else None,
        status=st, usable=st in service.USABLE,
    )


@router.get("", response_model=list[StandardOut])
def list_standards(q: str | None = None, category: str | None = None, include_inactive: bool = False,
                   ctx: TenantContext = Depends(require(P.STANDARDS_READ))):
    return [to_out(ctx, s) for s in service.list_standards(ctx, q, category, include_inactive)]


@router.post("", response_model=StandardOut, status_code=201)
def create_standard(body: StandardCreate, ctx: TenantContext = Depends(require(P.STANDARDS_MANAGE))):
    return to_out(ctx, service.create_standard(ctx, body.model_dump()))


@router.get("/{standard_id}", response_model=StandardOut)
def get_standard(standard_id: uuid.UUID, ctx: TenantContext = Depends(require(P.STANDARDS_READ))):
    return to_out(ctx, service.get_standard(ctx, standard_id))


@router.patch("/{standard_id}", response_model=StandardOut)
def update_standard(standard_id: uuid.UUID, body: StandardUpdate,
                    ctx: TenantContext = Depends(require(P.STANDARDS_MANAGE))):
    data = body.model_dump(exclude_unset=True)
    for required in ("description", "category", "plant_id", "calibration_frequency_days"):
        if required in data and data[required] is None:
            data.pop(required)
    return to_out(ctx, service.update_standard(ctx, standard_id, data))


@router.post("/{standard_id}/transitions", response_model=StandardOut)
def transition_standard(standard_id: uuid.UUID, body: TransitionIn,
                        ctx: TenantContext = Depends(require(P.STANDARDS_MANAGE))):
    return to_out(ctx, service.transition(ctx, standard_id, body.target, body.reason.strip()))


@router.get("/{standard_id}/certificates", response_model=list[CertificateOut])
def list_certificates(standard_id: uuid.UUID, ctx: TenantContext = Depends(require(P.STANDARDS_READ))):
    return service.certificates(ctx, standard_id)


@router.post("/{standard_id}/certificates", response_model=CertificateOut, status_code=201)
async def add_certificate(
    standard_id: uuid.UUID,
    certificate_number: str = Form(..., min_length=1, max_length=80),
    issuer: str = Form(..., min_length=2, max_length=200),
    calibration_date: date = Form(...),
    issue_date: date = Form(...),
    valid_until: date | None = Form(None),
    accreditation: str | None = Form(None, max_length=120),
    uncertainty: str | None = Form(None, max_length=200),
    traceability: str | None = Form(None, max_length=300),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require(P.STANDARDS_MANAGE)),
):
    meta = dict(certificate_number=certificate_number, issuer=issuer, calibration_date=calibration_date,
                issue_date=issue_date, valid_until=valid_until, accreditation=accreditation,
                uncertainty=uncertainty, traceability=traceability)
    return service.add_certificate(ctx, standard_id, meta, file.filename or "certificate.pdf", await file.read())
