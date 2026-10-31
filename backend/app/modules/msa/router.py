import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app import engine
from app.modules.configuration import registry, workflow
from app.modules.configuration import service as config
from app.modules.documents import service as documents
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.msa import guidance, service
from app.modules.msa.models import CRITERIA_SCOPES, DECISIONS, METHODS

router = APIRouter(tags=["msa"])
documents.register(service.ENTITY, P.MSA_READ, P.MSA_MANAGE, lambda ctx, i: service.get_study(ctx, i))
registry.register_field_entity(registry.FieldEntity(
    service.ENTITY, P.MSA_READ, P.MSA_MANAGE,
    ("study_code", "title", "method", "characteristic", "part_number", "part_revision", "customer", "gage_id",
     "responsible_id", "start_date", "end_date", "notes")))
registry.register_workflow_entity(registry.WorkflowEntity(
    entity_type=service.ENTITY,
    default_definition=service.DEFAULT_WORKFLOW,
    system_states={"DRAFT": "initial", "APPROVED": "terminal", "CANCELLED": "terminal"},
    capabilities=("configure", "capture", "calculate", "conclude", "report"),
    facts={"has_run": "boolean", "decision": "text", "final_decision": "text", "method": "text",
           "observation_count": "number", "has_report": "boolean", "has_customer": "boolean",
           "pct_sv_grr": "number", "ndc": "number", "cgk": "number", "min_kappa_vs_reference": "number"},
    load=service._load,
    get_state=lambda s: s.status,
    set_state=service._set_state,
    get_version=lambda s: s.workflow_version,
    compute_facts=service._facts,
    parties=lambda s: {"responsible": s.responsible_id, "created_by": s.created_by},
    before_enter=service._before_enter,
    after_enter=service._after_enter,
    plant_of=lambda s: s.plant_id,
    link_prefix="/msa/",
))

Method = Literal[METHODS]  # type: ignore[valid-type]


class Design(BaseModel):
    """Experimental design. Fields not relevant to the method are ignored by the engine."""

    model_config = ConfigDict(extra="forbid")
    operators: int | None = Field(default=None, ge=1, le=50)
    parts: int | None = Field(default=None, ge=1, le=500)
    parts_per_operator: int | None = Field(default=None, ge=1, le=100)
    trials: int | None = Field(default=None, ge=1, le=100)
    operator_names: list[str] | None = Field(default=None, max_length=50)
    part_ids: list[str] | None = Field(default=None, max_length=500)
    sequence: Literal["RANDOMIZED", "SEQUENTIAL", "BLIND"] | None = None
    unit: str | None = Field(default=None, max_length=20)
    tolerance: float | None = None
    lsl: float | None = None
    usl: float | None = None
    resolution: float | None = None
    reference: float | None = None
    subgroup_size: int | None = Field(default=None, ge=1, le=10)
    categories: list[str] | None = Field(default=None, max_length=20)
    part_reference: dict[str, str] | None = None
    accept_category: str | None = None
    reject_category: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_var_multiplier: float | None = None
    interaction_alpha: float | None = Field(default=None, gt=0, lt=1)
    interaction_mode: Literal["auto", "include", "exclude"] | None = None
    alpha: float | None = Field(default=None, gt=0, lt=1)
    k_percent: float | None = Field(default=None, gt=0, le=100)
    l_sigma: float | None = Field(default=None, gt=0)
    rules: dict[str, dict] | None = None


class StudyBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    characteristic: str = Field(min_length=1, max_length=200)
    part_number: str | None = Field(default=None, max_length=80)
    part_revision: str | None = Field(default=None, max_length=20)
    customer: str | None = Field(default=None, max_length=200)
    department_id: uuid.UUID | None = None
    end_date: date | None = None
    criteria_set_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class StudyCreate(StudyBase):
    method: Method
    plant_id: uuid.UUID
    gage_id: uuid.UUID
    responsible_id: uuid.UUID
    start_date: date
    design: Design = Field(default_factory=Design)
    params: Params = Field(default_factory=Params)
    custom_fields: dict[str, Any] | None = None


class StudyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    characteristic: str | None = Field(default=None, min_length=1, max_length=200)
    part_number: str | None = Field(default=None, max_length=80)
    part_revision: str | None = Field(default=None, max_length=20)
    customer: str | None = Field(default=None, max_length=200)
    method: Method | None = None
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    gage_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    criteria_set_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)
    design: Design | None = None
    params: Params | None = None


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    study_code: str
    title: str
    method: str
    status: str
    workflow_version: int
    characteristic: str
    part_number: str | None
    part_revision: str | None
    customer: str | None
    plant_id: uuid.UUID
    department_id: uuid.UUID | None
    gage_id: uuid.UUID
    gage_code: str | None = None
    gage_description: str | None = None
    responsible_id: uuid.UUID
    start_date: date
    end_date: date | None
    design: dict
    params: dict
    criteria_set_id: uuid.UUID | None
    notes: str | None
    final_decision: str | None
    final_comment: str | None
    concluded_by: uuid.UUID | None
    concluded_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    latest_decision: str | None = None


class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator: str | None = Field(default=None, max_length=60)
    part: str | None = Field(default=None, max_length=60)
    trial: int | None = None
    subgroup: int | None = None
    value: Decimal | float | str | None = None
    category: str | None = Field(default=None, max_length=60)
    reference: Decimal | float | str | None = None
    measured_at: datetime | None = None


class ObservationsIn(BaseModel):
    observations: list[ObservationIn] = Field(min_length=1, max_length=5000)


class CorrectionIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    replacement: ObservationIn | None = None


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    operator: str | None
    part: str | None
    trial: int | None
    subgroup: int | None
    value: Decimal | None
    category: str | None
    reference: Decimal | None
    measured_at: datetime | None
    source: str
    superseded: bool
    supersedes_id: uuid.UUID | None
    correction_reason: str | None
    recorded_by: uuid.UUID
    recorded_at: datetime

    @field_serializer("value", "reference")
    def _dec(self, v):
        return None if v is None else format(v.normalize(), "f")


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    study_id: uuid.UUID
    run_number: int
    method: str
    algorithm_version: str
    engine_version: str
    validation_status: str
    input_hash: str
    results: dict
    criteria_set_id: uuid.UUID | None
    criteria_snapshot: dict | None
    evaluation: list | None
    decision: str
    gage_snapshot: dict
    calculated_by: uuid.UUID
    calculated_at: datetime
    guidance: list = []


def _run_out(run) -> RunOut:
    out = RunOut.model_validate(run)
    out.guidance = guidance.guidance(run.method, run.results)
    return out


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_number: int
    algorithm_version: str
    engine_version: str
    validation_status: str
    input_hash: str
    decision: str
    calculated_by: uuid.UUID
    calculated_at: datetime


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1, max_length=60)
    op: Literal["lte", "lt", "gte", "gt", "eq"]
    value: float | bool
    outcome: Literal["NOT_ACCEPTABLE", "CONDITIONAL"] = "NOT_ACCEPTABLE"
    label: str | None = Field(default=None, max_length=120)


class CriteriaIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    method: Method
    scope: Literal[CRITERIA_SCOPES]  # type: ignore[valid-type]
    plant_id: uuid.UUID | None = None
    customer: str | None = Field(default=None, max_length=200)
    rules: list[Rule] = Field(min_length=1, max_length=30)
    source: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _bools(self):
        for r in self.rules:
            if isinstance(r.value, bool) and r.op != "eq":
                raise ValueError("boolean rules must use the 'eq' operator")
        return self


class CriteriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: int
    method: str
    scope: str
    plant_id: uuid.UUID | None
    customer: str | None
    rules: list[dict]
    source: str
    status: str
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    retired_at: datetime | None
    retired_reason: str | None


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ConclusionIn(BaseModel):
    decision: Literal[DECISIONS]  # type: ignore[valid-type]
    comment: str | None = Field(default=None, max_length=2000)


class ReportIn(BaseModel):
    run_id: uuid.UUID | None = None
    lang: Literal["es", "en"] | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    study_id: uuid.UUID
    run_id: uuid.UUID
    revision: int
    attachment_id: uuid.UUID
    issued_by: uuid.UUID
    issued_at: datetime


def _out(ctx: TenantContext, s) -> StudyOut:
    out = StudyOut.model_validate(s)
    out.gage_code, out.gage_description = s.gage.gage_code, s.gage.description
    run = service.latest_run(ctx, s)
    out.latest_decision = run.decision if run else None
    return out


def _clean(model: BaseModel | None) -> dict:
    return {} if model is None else model.model_dump(exclude_none=True)


# ---------------------------------------------------------------- engine catalogue

@router.get("/msa/methods")
def methods(_: TenantContext = Depends(require(P.MSA_READ))):
    return {"engine_version": engine.ENGINE_VERSION, "methods": engine.catalogue()}


# ---------------------------------------------------------------- studies

@router.get("/msa/studies", response_model=list[StudyOut])
def list_studies(gage_id: uuid.UUID | None = None, status: str | None = None, method: Method | None = None,
                 q: str | None = Query(default=None, max_length=100),
                 ctx: TenantContext = Depends(require(P.MSA_READ))):
    return [_out(ctx, s) for s in service.list_studies(ctx, gage_id=gage_id, status=status, method=method, q=q)]


@router.post("/msa/studies", response_model=StudyOut, status_code=201)
def create_study(body: StudyCreate, ctx: TenantContext = Depends(require(P.MSA_MANAGE))):
    data = body.model_dump(exclude={"custom_fields", "design", "params"})
    data["design"], data["params"] = _clean(body.design), _clean(body.params)
    return _out(ctx, service.create_study(ctx, data, body.custom_fields))


@router.get("/msa/studies/{study_id}", response_model=StudyOut)
def get_study(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return _out(ctx, service.get_study(ctx, study_id))


@router.patch("/msa/studies/{study_id}", response_model=StudyOut)
def update_study(study_id: uuid.UUID, body: StudyUpdate, ctx: TenantContext = Depends(require(P.MSA_MANAGE))):
    data = body.model_dump(exclude_unset=True, exclude={"design", "params"})
    if body.design is not None:
        data["design"] = _clean(body.design)
    if body.params is not None:
        data["params"] = _clean(body.params)
    return _out(ctx, service.update_study(ctx, study_id, data))


@router.get("/msa/studies/{study_id}/sequence")
def sequence(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.run_order(service.get_study(ctx, study_id))


@router.get("/msa/studies/{study_id}/observations", response_model=list[ObservationOut])
def list_observations(study_id: uuid.UUID, include_superseded: bool = False,
                      ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.observations(ctx, study_id, include_superseded)


@router.post("/msa/studies/{study_id}/observations", response_model=list[ObservationOut], status_code=201)
def add_observations(study_id: uuid.UUID, body: ObservationsIn, ctx: TenantContext = Depends(require(P.MSA_MANAGE))):
    return service.add_observations(ctx, study_id, [o.model_dump(exclude_none=True) for o in body.observations])


@router.post("/msa/observations/{obs_id}/correct", response_model=ObservationOut | None)
def correct_observation(obs_id: uuid.UUID, body: CorrectionIn, ctx: TenantContext = Depends(require(P.MSA_MANAGE))):
    row = body.replacement.model_dump(exclude_none=True) if body.replacement else None
    return service.correct_observation(ctx, obs_id, row, body.reason)


@router.get("/msa/studies/{study_id}/validation")
def validate(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.validate_data(ctx, study_id)


@router.post("/msa/studies/{study_id}/calculate", response_model=RunOut, status_code=201)
def calculate(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_CALCULATE))):
    return _run_out(service.calculate(ctx, study_id))


@router.get("/msa/studies/{study_id}/runs", response_model=list[RunSummary])
def list_runs(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.runs(ctx, study_id)


@router.get("/msa/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return _run_out(service.get_run(ctx, run_id))


@router.post("/msa/runs/{run_id}/verify")
def verify_run(run_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.verify_run(ctx, run_id)


@router.post("/msa/studies/{study_id}/conclusion", response_model=StudyOut)
def conclude(study_id: uuid.UUID, body: ConclusionIn, ctx: TenantContext = Depends(require(P.MSA_APPROVE))):
    return _out(ctx, service.set_conclusion(ctx, study_id, body.decision, body.comment))


@router.post("/msa/studies/{study_id}/reports", response_model=ReportOut, status_code=201)
def issue_report(study_id: uuid.UUID, body: ReportIn, ctx: TenantContext = Depends(require(P.MSA_MANAGE))):
    return service.issue_report(ctx, study_id, body.run_id, body.lang)


@router.get("/msa/studies/{study_id}/reports", response_model=list[ReportOut])
def list_reports(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.reports(ctx, study_id)


@router.get("/msa/studies/{study_id}/custom-fields")
def custom_fields(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    service.get_study(ctx, study_id)
    return config.field_values(ctx, service.ENTITY, study_id)


@router.get("/msa/studies/{study_id}/workflow")
def study_workflow(study_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_READ))):
    study = service.get_study(ctx, study_id)
    return {"state": study.status, "transitions": workflow.available(ctx, service.ENTITY, study, study.id)}


# ---------------------------------------------------------------- acceptance criteria

@router.get("/msa/criteria", response_model=list[CriteriaOut])
def list_criteria(method: Method | None = None, include_retired: bool = False,
                  ctx: TenantContext = Depends(require(P.MSA_READ))):
    return service.list_criteria(ctx, method, include_retired)


@router.get("/msa/criteria/templates")
def criteria_templates(_: TenantContext = Depends(require(P.MSA_READ))):
    return service.CRITERIA_TEMPLATES


@router.post("/msa/criteria", response_model=CriteriaOut, status_code=201)
def create_criteria(body: CriteriaIn, ctx: TenantContext = Depends(require(P.MSA_CRITERIA))):
    data = body.model_dump()
    data["rules"] = [r.model_dump(exclude_none=True) for r in body.rules]
    return service.create_criteria(ctx, data)


@router.post("/msa/criteria/{criteria_id}/approve", response_model=CriteriaOut)
def approve_criteria(criteria_id: uuid.UUID, ctx: TenantContext = Depends(require(P.MSA_APPROVE))):
    return service.approve_criteria(ctx, criteria_id)


@router.post("/msa/criteria/{criteria_id}/retire", response_model=CriteriaOut)
def retire_criteria(criteria_id: uuid.UUID, body: ReasonIn, ctx: TenantContext = Depends(require(P.MSA_CRITERIA))):
    return service.retire_criteria(ctx, criteria_id, body.reason)
