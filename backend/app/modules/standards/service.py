"""Standards Management.

Effective status of a standard (shown to users and checked before use):

==============================================  ===========
Condition                                       Status
==============================================  ===========
control_status INACTIVE / RESTRICTED            INACTIVE / RESTRICTED
no current certificate                          NO_CERTIFICATE
valid_until < date                              EXPIRED
date <= valid_until <= date + due-soon window   DUE_SOON
otherwise                                       VALID
==============================================  ===========

Only VALID and DUE_SOON standards can be used. Any other status requires a documented
exception by a user with ``standards:exception``.
"""

import uuid
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.audit import service as audit
from app.modules.documents import service as documents
from app.modules.gages.service import ensure_active_member
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.organizations.router import get_plant
from app.modules.standards.models import Standard, StandardCertificate


class StandardStatus(StrEnum):
    VALID = "VALID"
    DUE_SOON = "DUE_SOON"
    EXPIRED = "EXPIRED"
    NO_CERTIFICATE = "NO_CERTIFICATE"
    RESTRICTED = "RESTRICTED"
    INACTIVE = "INACTIVE"


USABLE = {StandardStatus.VALID, StandardStatus.DUE_SOON}
FIELDS = ["standard_code", "description", "category", "subtype", "plant_id", "manufacturer", "model",
          "serial_number", "range_min", "range_max", "unit", "resolution", "accuracy", "location",
          "custodian_user_id", "calibration_frequency_days", "notes"]


def status_on(s: Standard, on: date, window: int) -> StandardStatus:
    if s.control_status == "INACTIVE":
        return StandardStatus.INACTIVE
    if s.control_status == "RESTRICTED":
        return StandardStatus.RESTRICTED
    if s.current_certificate_id is None or s.valid_until is None:
        return StandardStatus.NO_CERTIFICATE
    if s.valid_until < on:
        return StandardStatus.EXPIRED
    if s.valid_until <= on + timedelta(days=window):
        return StandardStatus.DUE_SOON
    return StandardStatus.VALID


def status(ctx: TenantContext, s: Standard) -> StandardStatus:
    return status_on(s, ctx.today(), ctx.organization.due_soon_days)


def get_standard(ctx: TenantContext, standard_id: uuid.UUID, *, for_update: bool = False) -> Standard:
    stmt = select(Standard).where(Standard.id == standard_id, Standard.organization_id == ctx.organization_id)
    if for_update:
        stmt = stmt.with_for_update(of=Standard)
    s = ctx.db.scalar(stmt)
    if s is None or not ctx.can_access_plant(s.plant_id):
        raise NotFoundError("Standard not found")
    return s


def list_standards(ctx: TenantContext, q: str | None, category: str | None, include_inactive: bool) -> list[Standard]:
    stmt = select(Standard).where(Standard.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(Standard.plant_id.in_(ctx.plant_ids))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Standard.standard_code.ilike(like) | Standard.description.ilike(like)
                          | Standard.serial_number.ilike(like))
    if category:
        stmt = stmt.where(Standard.category == category)
    if not include_inactive:
        stmt = stmt.where(Standard.control_status != "INACTIVE")
    return list(ctx.db.scalars(stmt.order_by(Standard.standard_code)).unique())


def _validate(ctx: TenantContext, data: dict) -> None:
    if data.get("plant_id"):
        get_plant(ctx, data["plant_id"])
    if data.get("custodian_user_id"):
        ensure_active_member(ctx, data["custodian_user_id"], "invalid_custodian")


def create_standard(ctx: TenantContext, data: dict) -> Standard:
    data["standard_code"] = data["standard_code"].strip().upper()
    _validate(ctx, data)
    if ctx.db.scalar(select(Standard.id).where(Standard.organization_id == ctx.organization_id,
                                               Standard.standard_code == data["standard_code"])):
        raise ConflictError("Standard ID already exists in this organization", code="duplicate_standard_code")
    s = Standard(organization_id=ctx.organization_id, created_by=ctx.user_id, **data)
    ctx.db.add(s)
    ctx.db.flush()
    ctx.audit(action="standard.created", entity_type="standard", entity_id=s.id, changes=audit.snapshot(s, FIELDS))
    ctx.db.commit()
    return get_standard(ctx, s.id)


def update_standard(ctx: TenantContext, standard_id: uuid.UUID, data: dict) -> Standard:
    s = get_standard(ctx, standard_id, for_update=True)
    if s.control_status == "INACTIVE":
        raise ConflictError("Inactive standards cannot be edited", code="standard_inactive")
    data = {k: v for k, v in data.items() if audit.plain(getattr(s, k)) != audit.plain(v)}
    if not data:
        return s
    _validate(ctx, data)
    rmin, rmax = data.get("range_min", s.range_min), data.get("range_max", s.range_max)
    if rmin is not None and rmax is not None and rmin > rmax:
        raise BusinessRuleError("range_min must be less than or equal to range_max", code="invalid_range")
    before = audit.snapshot(s, FIELDS)
    for k, v in data.items():
        setattr(s, k, v)
    ctx.audit(action="standard.updated", entity_type="standard", entity_id=s.id,
              changes=audit.diff(before, audit.snapshot(s, FIELDS)))
    ctx.db.commit()
    return get_standard(ctx, s.id)


TRANSITIONS = {("ACTIVE", "RESTRICTED"), ("RESTRICTED", "ACTIVE"), ("ACTIVE", "INACTIVE"),
               ("RESTRICTED", "INACTIVE"), ("INACTIVE", "ACTIVE")}


def transition(ctx: TenantContext, standard_id: uuid.UUID, target: str, reason: str) -> Standard:
    s = get_standard(ctx, standard_id, for_update=True)
    if (s.control_status, target) not in TRANSITIONS:
        raise BusinessRuleError(f"Transition {s.control_status} -> {target} is not allowed", code="invalid_transition")
    before = status(ctx, s)
    prev = s.control_status
    s.control_status = target
    ctx.audit(action="standard.status_changed", entity_type="standard", entity_id=s.id, reason=reason,
              changes={"control_status": [prev, target], "status": [before.value, status(ctx, s).value]})
    ctx.db.commit()
    return get_standard(ctx, s.id)


def add_certificate(ctx: TenantContext, standard_id: uuid.UUID, meta: dict, filename: str, data: bytes) -> StandardCertificate:
    """Register a new certificate (PDF). The previous current certificate becomes SUPERSEDED."""
    s = get_standard(ctx, standard_id, for_update=True)
    if s.control_status == "INACTIVE":
        raise ConflictError("Inactive standards cannot receive certificates", code="standard_inactive")
    today = ctx.today()
    if meta["calibration_date"] > today or meta["issue_date"] > today:
        raise BusinessRuleError("Certificate dates cannot be in the future", code="future_date")
    if meta["issue_date"] < meta["calibration_date"]:
        raise BusinessRuleError("Issue date cannot precede the calibration date", code="invalid_dates")
    valid_until = meta.get("valid_until") or meta["calibration_date"] + timedelta(days=s.calibration_frequency_days)
    if valid_until <= meta["calibration_date"]:
        raise BusinessRuleError("valid_until must be after the calibration date", code="invalid_dates")
    current = ctx.db.get(StandardCertificate, s.current_certificate_id) if s.current_certificate_id else None
    if current and meta["calibration_date"] < current.calibration_date:
        raise BusinessRuleError("A newer certificate is already current", code="certificate_regression")

    att = documents.store(ctx, entity_type="standard", entity_id=s.id, category="CERTIFICATE",
                          filename=filename, data=data, title=meta["certificate_number"], locked=True, pdf_only=True)
    cert = StandardCertificate(
        organization_id=ctx.organization_id, standard_id=s.id, attachment_id=att.id, created_by=ctx.user_id,
        certificate_number=meta["certificate_number"].strip(), issuer=meta["issuer"].strip(),
        accreditation=meta.get("accreditation"), calibration_date=meta["calibration_date"],
        issue_date=meta["issue_date"], valid_until=valid_until, uncertainty=meta.get("uncertainty"),
        traceability=meta.get("traceability"),
    )
    ctx.db.add(cert)
    ctx.db.flush()
    if current:
        current.status = "SUPERSEDED"
    before = audit.snapshot(s, ["last_calibration_date", "valid_until"])
    s.current_certificate_id = cert.id
    s.last_calibration_date = cert.calibration_date
    s.valid_until = cert.valid_until
    ctx.audit(action="standard.certificate_added", entity_type="standard", entity_id=s.id,
              changes=audit.diff(before, audit.snapshot(s, ["last_calibration_date", "valid_until"]))
              | {"certificate": cert.certificate_number, "superseded": current.certificate_number if current else None})
    ctx.db.commit()
    return cert


def certificates(ctx: TenantContext, standard_id: uuid.UUID) -> list[StandardCertificate]:
    get_standard(ctx, standard_id)
    return list(ctx.db.scalars(select(StandardCertificate).where(StandardCertificate.standard_id == standard_id)
                               .order_by(StandardCertificate.calibration_date.desc(), StandardCertificate.created_at.desc())))


def check_usable(ctx: TenantContext, standard_id: uuid.UUID, on: date, exception_reason: str | None) -> dict:
    """Validate a standard for use on ``on`` and return a snapshot of its condition.

    Raises unless the standard is usable or a documented exception is given by an
    authorized user. The snapshot is stored with the usage so the condition at that
    date can be reconstructed even if the standard changes later.
    """
    s = get_standard(ctx, standard_id)
    st = status_on(s, on, ctx.organization.due_soon_days)
    snapshot = {
        "standard_code": s.standard_code,
        "status": st.value,
        "certificate_id": str(s.current_certificate_id) if s.current_certificate_id else None,
        "valid_until": s.valid_until.isoformat() if s.valid_until else None,
        "exception": False,
    }
    if st in USABLE:
        return snapshot
    if not exception_reason:
        raise BusinessRuleError(
            f"Standard {s.standard_code} is {st.value} and cannot be used without an authorized exception",
            code="standard_not_usable", details={"standard": s.standard_code, "status": st.value},
        )
    ctx.ensure(P.STANDARDS_EXCEPTION)
    snapshot["exception"] = True
    return snapshot
