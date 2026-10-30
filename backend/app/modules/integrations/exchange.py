"""Versioned read contracts for external systems (``/api/v1/exchange/...``).

Each resource has an explicit, stable field list (contract v1) independent of the
internal models, tenant and plant scoping, pagination and filters (``updated_since``,
``status``, ``gage_id``). Changing a contract means publishing v2, never altering v1.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.modules.audit.service import plain
from app.modules.calibration.models import CalibrationActivity
from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.laboratory.models import InspectionResult, ServiceRequest, WorkOrder
from app.modules.msa.models import MsaStudy
from app.modules.oot.models import OotCase

CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class Resource:
    model: type
    permission: str
    fields: tuple[str, ...]
    plant_column: str | None = "plant_id"
    updated_column: str = "updated_at"
    status_column: str | None = "status"
    gage_column: str | None = "gage_id"


RESOURCES: dict[str, Resource] = {
    "gages": Resource(Gage, P.GAGES_READ, (
        "id", "gage_code", "description", "gage_type_id", "plant_id", "department_id", "manufacturer", "model",
        "serial_number", "range_min", "range_max", "unit", "resolution", "criticality", "location",
        "responsible_user_id", "control_status", "calibration_frequency_days", "last_calibration_date",
        "next_due_date", "updated_at"), status_column="control_status", gage_column="id"),
    "calibrations": Resource(CalibrationActivity, P.CALIBRATION_READ, (
        "id", "calibration_code", "gage_id", "plant_id", "activity_type", "status", "planned_date", "scheduled_date",
        "performed_date", "result", "as_found_in_tolerance", "as_left_in_tolerance", "due_date", "released_at",
        "updated_at")),
    "service-requests": Resource(ServiceRequest, P.LAB_READ, (
        "id", "request_code", "plant_id", "customer_type", "customer_name", "service_id", "part_number",
        "part_revision", "quantity", "priority", "requested_date", "committed_date", "status", "updated_at"),
        gage_column=None),
    "work-orders": Resource(WorkOrder, P.LAB_READ, (
        "id", "work_order_code", "service_request_id", "plant_id", "technician_id", "priority", "scheduled_start",
        "scheduled_end", "status", "started_at", "completed_at", "due_date", "updated_at"), gage_column=None),
    "inspection-results": Resource(InspectionResult, P.LAB_READ, (
        "id", "work_order_id", "part_number", "drawing_revision", "sample_id", "characteristic_number",
        "characteristic", "nominal", "lower_limit", "upper_limit", "measured", "unit", "gage_id", "gage_status",
        "result", "measured_at", "superseded"), plant_column=None, updated_column="measured_at", status_column=None),
    "msa-studies": Resource(MsaStudy, P.MSA_READ, (
        "id", "study_code", "title", "method", "status", "characteristic", "part_number", "part_revision",
        "customer", "gage_id", "plant_id", "start_date", "end_date", "final_decision", "updated_at")),
    "oot-cases": Resource(OotCase, P.OOT_READ, (
        "id", "case_code", "gage_id", "plant_id", "calibration_id", "detected_on", "status", "restriction_applied",
        "risk_level", "impact_start", "impact_end", "gage_released_at", "closed_at", "updated_at")),
}


def page(ctx: TenantContext, resource: str, *, page_no: int, page_size: int, updated_since: datetime | None,
         status: str | None, gage_id: uuid.UUID | None) -> dict:
    res = RESOURCES.get(resource)
    if res is None:
        raise NotFoundError("Unknown resource")
    ctx.ensure(res.permission)
    m = res.model
    stmt = select(m).where(m.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        if res.plant_column:
            stmt = stmt.where(getattr(m, res.plant_column).in_(ctx.plant_ids))
        elif m is InspectionResult:
            stmt = stmt.join(Gage, Gage.id == InspectionResult.gage_id).where(Gage.plant_id.in_(ctx.plant_ids))
    if updated_since:
        stmt = stmt.where(getattr(m, res.updated_column) > updated_since)
    if status and res.status_column:
        stmt = stmt.where(getattr(m, res.status_column) == status)
    if gage_id and res.gage_column:
        stmt = stmt.where(getattr(m, res.gage_column) == gage_id)
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = ctx.db.scalars(stmt.order_by(getattr(m, res.updated_column), m.id)
                          .offset((page_no - 1) * page_size).limit(page_size)).all()
    items = []
    for r in rows:
        item = {f: plain(getattr(r, f)) for f in res.fields}
        if m is Gage:
            item["status"] = gages.current_status(ctx, r).value
        items.append(item)
    return {"contract_version": CONTRACT_VERSION, "resource": resource, "items": items, "page": page_no,
            "page_size": page_size, "total": total,
            "next_page": page_no + 1 if page_no * page_size < total else None}
