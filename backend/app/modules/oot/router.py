import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.configuration import registry
from app.modules.documents import service as documents
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.oot import service
from app.modules.oot.models import ACTION_TYPES, ASSESSMENTS, CLOSE_REQUIREMENTS, RISK_LEVELS

router = APIRouter(tags=["oot"])
documents.register(service.ENTITY, P.OOT_READ, P.OOT_MANAGE, lambda ctx, i: service.get_case(ctx, i))
registry.register_field_entity(registry.FieldEntity(
    service.ENTITY, P.OOT_READ, P.OOT_MANAGE,
    ("case_code", "gage_id", "calibration_id", "detected_on", "description", "found_result", "tolerance",
     "max_deviation", "responsible_id", "risk_level", "risk_assessment", "disposition")))
registry.register_workflow_entity(registry.WorkflowEntity(
    entity_type=service.ENTITY,
    default_definition=service.DEFAULT_WORKFLOW,
    system_states={"DETECTED": "initial", "RESTRICTED": "state", "CLOSED": "terminal", "CANCELLED": "terminal"},
    capabilities=("investigate", "analyze", "act", "release_gage"),
    facts={"risk_level": "text", "has_risk_assessment": "boolean", "has_disposition": "boolean",
           "has_corrective_actions": "boolean", "open_actions": "number", "pending_impact_items": "number",
           "impacted_items": "number", "analysis_generated": "boolean", "customer_notification_required": "boolean",
           "customer_notified": "boolean", "gage_released": "boolean", "max_deviation": "number"},
    load=service._load,
    get_state=lambda c: c.status,
    set_state=service._set_state,
    get_version=lambda c: c.workflow_version,
    compute_facts=service._facts,
    parties=lambda c: {"responsible": c.responsible_id, "created_by": c.created_by},
    before_enter=service._before_enter,
    after_enter=service._after_enter,
    plant_of=lambda c: c.plant_id,
    link_prefix="/oot/",
))


def _dec(v):
    return None if v is None else format(v.normalize(), "f")


class CaseCreate(BaseModel):
    gage_id: uuid.UUID
    calibration_id: uuid.UUID | None = None
    detected_on: date
    description: str = Field(min_length=5, max_length=4000)
    responsible_id: uuid.UUID
    found_result: str | None = Field(default=None, max_length=500)
    tolerance: str | None = Field(default=None, max_length=200)
    max_deviation: Decimal | None = None
    custom_fields: dict[str, Any] | None = None


class InvestigationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = Field(default=None, min_length=5, max_length=4000)
    responsible_id: uuid.UUID | None = None
    risk_level: Literal[RISK_LEVELS] | None = None  # type: ignore[valid-type]
    risk_assessment: str | None = Field(default=None, max_length=8000)
    investigation_scope: str | None = Field(default=None, max_length=8000)
    reinspection: str | None = Field(default=None, max_length=8000)
    containment: str | None = Field(default=None, max_length=8000)
    disposition: str | None = Field(default=None, max_length=8000)
    corrective_actions: str | None = Field(default=None, max_length=8000)
    customer_notification_required: bool | None = None
    customer_notification: str | None = Field(default=None, max_length=8000)
    customer_notified_on: date | None = None
    limitations: str | None = Field(default=None, max_length=8000)


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_code: str
    plant_id: uuid.UUID
    gage_id: uuid.UUID
    gage_code: str | None = None
    gage_description: str | None = None
    gage_control_status: str | None = None
    calibration_id: uuid.UUID | None
    detection_source: str
    detected_on: date
    description: str
    found_result: str | None
    tolerance: str | None
    max_deviation: Decimal | None
    as_found: list | None
    as_left: list | None
    responsible_id: uuid.UUID
    status: str
    workflow_version: int
    restriction_applied: bool
    gage_prior_control_status: str | None
    gage_released_at: datetime | None
    gage_released_by: uuid.UUID | None
    gage_release_reason: str | None
    last_acceptable_calibration_id: uuid.UUID | None
    impact_start: date | None
    impact_end: date | None
    analysis_generated_at: datetime | None
    limitations: str | None
    risk_level: str | None
    risk_assessment: str | None
    investigation_scope: str | None
    reinspection: str | None
    containment: str | None
    disposition: str | None
    corrective_actions: str | None
    customer_notification_required: bool | None
    customer_notification: str | None
    customer_notified_on: date | None
    closed_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    close_gaps: list[str] = []

    @field_serializer("max_deviation")
    def _ser(self, v):
        return _dec(v)


class ItemIn(BaseModel):
    ref_code: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=3, max_length=1000)
    occurred_at: datetime | None = None
    data: dict | None = None


class AssessIn(BaseModel):
    assessment: Literal[ASSESSMENTS]  # type: ignore[valid-type]
    note: str | None = Field(default=None, max_length=2000)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_type: str
    source: str
    ref_id: uuid.UUID | None
    ref_code: str | None
    description: str
    occurred_at: datetime | None
    data: dict | None
    assessment: str
    assessment_note: str | None
    assessed_by: uuid.UUID | None
    assessed_at: datetime | None


class ActionIn(BaseModel):
    action_type: Literal[ACTION_TYPES]  # type: ignore[valid-type]
    description: str = Field(min_length=3, max_length=2000)
    owner_id: uuid.UUID
    due_date: date | None = None


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_type: str
    description: str
    owner_id: uuid.UUID
    due_date: date | None
    status: str
    result_note: str | None
    completed_by: uuid.UUID | None
    completed_at: datetime | None
    created_at: datetime


class FinishIn(BaseModel):
    done: bool = True
    note: str = Field(min_length=3, max_length=2000)


class ReleaseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class SettingsIn(BaseModel):
    restrict_on_detection: bool
    auto_create_from_calibration: bool
    close_requirements: list[Literal[CLOSE_REQUIREMENTS]]  # type: ignore[valid-type]


def _out(ctx: TenantContext, c) -> CaseOut:
    out = CaseOut.model_validate(c)
    out.gage_code, out.gage_description, out.gage_control_status = (c.gage.gage_code, c.gage.description,
                                                                    c.gage.control_status)
    out.close_gaps = service.close_gaps(ctx, c)
    return out


@router.get("/oot/settings")
def get_settings(ctx: TenantContext = Depends(require(P.OOT_READ))):
    s = service.settings(ctx)
    return {"restrict_on_detection": s.restrict_on_detection, "auto_create_from_calibration":
            s.auto_create_from_calibration, "close_requirements": s.close_requirements, "version": s.version,
            "available_requirements": list(CLOSE_REQUIREMENTS)}


@router.put("/oot/settings")
def put_settings(body: SettingsIn, ctx: TenantContext = Depends(require(P.OOT_APPROVE))):
    service.update_settings(ctx, body.model_dump())
    return get_settings(ctx)


@router.get("/oot/cases", response_model=list[CaseOut])
def list_cases(gage_id: uuid.UUID | None = None, status: str | None = None, open_only: bool = False,
               ctx: TenantContext = Depends(require(P.OOT_READ))):
    return [_out(ctx, c) for c in service.list_cases(ctx, gage_id=gage_id, status=status, open_only=open_only)]


@router.post("/oot/cases", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return _out(ctx, service.create_manual(ctx, body.model_dump()))


@router.get("/oot/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: uuid.UUID, ctx: TenantContext = Depends(require(P.OOT_READ))):
    return _out(ctx, service.get_case(ctx, case_id))


@router.patch("/oot/cases/{case_id}", response_model=CaseOut)
def update_case(case_id: uuid.UUID, body: InvestigationIn, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return _out(ctx, service.update_investigation(ctx, case_id, body.model_dump(exclude_unset=True)))


@router.post("/oot/cases/{case_id}/analysis", response_model=CaseOut)
def analysis(case_id: uuid.UUID, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return _out(ctx, service.generate_analysis(ctx, case_id))


@router.get("/oot/cases/{case_id}/items", response_model=list[ItemOut])
def list_items(case_id: uuid.UUID, ctx: TenantContext = Depends(require(P.OOT_READ))):
    return service.items(ctx, case_id)


@router.post("/oot/cases/{case_id}/items", response_model=ItemOut, status_code=201)
def add_item(case_id: uuid.UUID, body: ItemIn, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return service.add_manual_item(ctx, case_id, body.model_dump())


@router.post("/oot/items/{item_id}/assess", response_model=ItemOut)
def assess(item_id: uuid.UUID, body: AssessIn, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return service.assess_item(ctx, item_id, body.assessment, body.note)


@router.get("/oot/cases/{case_id}/actions", response_model=list[ActionOut])
def list_actions(case_id: uuid.UUID, ctx: TenantContext = Depends(require(P.OOT_READ))):
    return service.actions(ctx, case_id)


@router.post("/oot/cases/{case_id}/actions", response_model=ActionOut, status_code=201)
def add_action(case_id: uuid.UUID, body: ActionIn, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return service.add_action(ctx, case_id, body.model_dump())


@router.post("/oot/actions/{action_id}/finish", response_model=ActionOut)
def finish_action(action_id: uuid.UUID, body: FinishIn, ctx: TenantContext = Depends(require(P.OOT_MANAGE))):
    return service.finish_action(ctx, action_id, body.done, body.note)


@router.post("/oot/cases/{case_id}/release-gage", response_model=CaseOut)
def release_gage(case_id: uuid.UUID, body: ReleaseIn, ctx: TenantContext = Depends(require(P.OOT_APPROVE))):
    return _out(ctx, service.release_gage(ctx, case_id, body.reason))


@router.get("/oot/cases/{case_id}/calibration-history")
def calibration_history(case_id: uuid.UUID, ctx: TenantContext = Depends(require(P.OOT_READ, P.CALIBRATION_READ))):
    from sqlalchemy import select

    from app.modules.calibration.models import CalibrationActivity

    case = service.get_case(ctx, case_id)
    rows = ctx.db.scalars(select(CalibrationActivity).where(
        CalibrationActivity.gage_id == case.gage_id, CalibrationActivity.organization_id == ctx.organization_id)
        .order_by(CalibrationActivity.performed_date.desc().nulls_last(), CalibrationActivity.created_at.desc()))
    return [{"id": a.id, "calibration_code": a.calibration_code, "activity_type": a.activity_type,
             "status": a.status, "performed_date": a.performed_date, "result": a.result,
             "as_found_in_tolerance": a.as_found_in_tolerance, "as_left_in_tolerance": a.as_left_in_tolerance,
             "is_last_acceptable": a.id == case.last_acceptable_calibration_id,
             "is_detection": a.id == case.calibration_id} for a in rows]
