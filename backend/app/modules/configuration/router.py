import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.competency.models import ACTIVITIES
from app.modules.configuration import definitions as defs
from app.modules.configuration import registry, service, workflow
from app.modules.configuration.models import KINDS
from app.modules.gages.service import AUDITED_FIELDS as GAGE_FIELDS
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import PERMISSIONS, SYSTEM_ROLES, P

router = APIRouter(tags=["configuration"])

# Existing records that accept custom fields (MSA studies and OOT cases register themselves).
registry.register_field_entity(registry.FieldEntity("gage", P.GAGES_READ, P.GAGES_UPDATE, tuple(GAGE_FIELDS)))
registry.register_field_entity(registry.FieldEntity(
    "calibration", P.CALIBRATION_READ, P.CALIBRATION_EXECUTE,
    ("calibration_code", "activity_type", "planned_date", "scheduled_date", "provider_name", "technician_id",
     "performed_date", "method", "uncertainty", "observations")))
registry.register_field_entity(registry.FieldEntity(
    "standard", P.STANDARDS_READ, P.STANDARDS_MANAGE, ("code", "description", "serial_number", "status")))
registry.register_field_entity(registry.FieldEntity(
    "service_request", P.LAB_READ, P.LAB_MANAGE,
    ("request_code", "customer_name", "part_number", "part_revision", "quantity", "description", "priority")))

Kind = Literal[KINDS]  # type: ignore[valid-type]


class VersionOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    definition: dict
    change_summary: str
    created_by: uuid.UUID
    created_at: datetime
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_comment: str | None

    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    key: str
    entity_type: str
    active_version: int | None
    is_retired: bool
    active: VersionOut | None
    draft: VersionOut | None
    version_count: int


class ProposeIn(BaseModel):
    kind: Kind
    definition: dict
    change_summary: str = Field(min_length=3, max_length=1000)


class DecisionIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ValuesIn(BaseModel):
    values: dict[str, Any]


class TransitionIn(BaseModel):
    transition: str = Field(min_length=2, max_length=40)
    comment: str | None = Field(default=None, max_length=2000)


def _item_out(row: dict) -> ItemOut:
    item = row["item"]
    return ItemOut(id=item.id, kind=item.kind, key=item.key, entity_type=item.entity_type,
                   active_version=item.active_version, is_retired=item.is_retired,
                   active=VersionOut.model_validate(row["active"]) if row["active"] else None,
                   draft=VersionOut.model_validate(row["draft"]) if row["draft"] else None,
                   version_count=row["version_count"])


@router.get("/config/catalogue")
def catalogue(ctx: TenantContext = Depends(require(P.CONFIG_READ))):
    return {
        "kinds": list(KINDS),
        "needs_approval": sorted(defs.NEEDS_APPROVAL),
        "field_types": list(defs.FIELD_TYPES),
        "text_formats": list(defs.TEXT_FORMATS),
        "operators": list(defs.OPERATORS),
        "field_entities": {k: list(v.builtin_fields) for k, v in registry.FIELD_ENTITIES.items()},
        "workflow_entities": {k: {"system_states": v.system_states, "capabilities": list(v.capabilities),
                                  "facts": v.facts, "default_definition": v.default_definition}
                              for k, v in registry.WORKFLOW_ENTITIES.items()},
        "approval_entities": list(registry.APPROVAL_ENTITIES),
        "approval_actions": list(registry.APPROVAL_ACTIONS),
        "permissions": sorted(PERMISSIONS),
        "roles": sorted(SYSTEM_ROLES),
        "activities": list(ACTIVITIES),
    }


@router.get("/config/items", response_model=list[ItemOut])
def list_items(kind: Kind | None = None, entity_type: str | None = None,
               ctx: TenantContext = Depends(require(P.CONFIG_READ))):
    return [_item_out(r) for r in service.list_items(ctx, kind, entity_type)]


@router.post("/config/items", response_model=VersionOut, status_code=201)
def propose(body: ProposeIn, ctx: TenantContext = Depends(require(P.CONFIG_MANAGE))):
    return service.propose(ctx, body.kind, body.definition, body.change_summary)


@router.get("/config/items/{item_id}/versions", response_model=list[VersionOut])
def item_versions(item_id: uuid.UUID, ctx: TenantContext = Depends(require(P.CONFIG_READ))):
    return service.versions(ctx, item_id)


@router.post("/config/items/{item_id}/retire", response_model=ItemOut)
def retire(item_id: uuid.UUID, body: ReasonIn, ctx: TenantContext = Depends(require(P.CONFIG_MANAGE))):
    service.retire(ctx, item_id, body.reason)
    return next(_item_out(r) for r in service.list_items(ctx, None, None) if r["item"].id == item_id)


@router.post("/config/versions/{version_id}/approve", response_model=VersionOut)
def approve(version_id: uuid.UUID, body: DecisionIn, ctx: TenantContext = Depends(require(P.CONFIG_APPROVE))):
    return service.decide(ctx, version_id, True, body.comment)


@router.post("/config/versions/{version_id}/reject", response_model=VersionOut)
def reject(version_id: uuid.UUID, body: DecisionIn, ctx: TenantContext = Depends(require(P.CONFIG_APPROVE))):
    return service.decide(ctx, version_id, False, body.comment)


# ---------------------------------------------------------------- custom fields and forms

@router.get("/custom-fields/{entity_type}")
def field_definitions(entity_type: str, ctx: TenantContext = Depends(require())):
    if entity_type not in registry.FIELD_ENTITIES:
        return []
    return service.field_definitions(ctx, entity_type)


@router.get("/custom-fields/{entity_type}/{entity_id}")
def field_values(entity_type: str, entity_id: uuid.UUID, ctx: TenantContext = Depends(require())):
    service.ensure_field_entity_access(ctx, entity_type, entity_id, write=False)
    return service.field_values(ctx, entity_type, entity_id)


@router.put("/custom-fields/{entity_type}/{entity_id}")
def set_field_values(entity_type: str, entity_id: uuid.UUID, body: ValuesIn, ctx: TenantContext = Depends(require())):
    service.ensure_field_entity_access(ctx, entity_type, entity_id, write=True)
    values = service.apply_values(ctx, entity_type, entity_id, body.values)
    ctx.db.commit()
    return values


@router.get("/forms/{entity_type}")
def form(entity_type: str, ctx: TenantContext = Depends(require())):
    ent = registry.FIELD_ENTITIES.get(entity_type)
    if ent is None:
        return {"entity_type": entity_type, "version": None, "sections": []}
    found = service.active_definition(ctx, "FORM", entity_type)
    if found:
        return {"entity_type": entity_type, "version": found[0], "sections": found[1]["sections"]}
    custom = [d["key"] for d in service.field_definitions(ctx, entity_type)]
    return {"entity_type": entity_type, "version": None,
            "sections": [{"title": "Custom fields", "fields": custom}] if custom else []}


# ---------------------------------------------------------------- workflows

@router.get("/workflows/{entity_type}/definition")
def workflow_definition(entity_type: str, ctx: TenantContext = Depends(require(P.CONFIG_READ))):
    version = workflow.version_for_new(ctx, entity_type)
    return {"version": version, "definition": workflow.definition(ctx, entity_type, version)}


@router.get("/workflows/{entity_type}/{entity_id}")
def workflow_state(entity_type: str, entity_id: uuid.UUID, ctx: TenantContext = Depends(require())):
    ent = workflow.entity(entity_type)
    record = ent.load(ctx, entity_id)
    version = ent.get_version(record)
    defn = workflow.definition(ctx, entity_type, version)
    return {
        "state": ent.get_state(record), "version": version,
        "states": defn["states"],
        "capabilities": sorted(workflow.capabilities(ctx, entity_type, record)),
        "transitions": workflow.available(ctx, entity_type, record, entity_id),
        "history": [{"event_type": e.event_type, "transition": e.transition, "action": e.action,
                     "from_state": e.from_state, "to_state": e.to_state, "comment": e.comment,
                     "actor_id": e.actor_id, "occurred_at": e.occurred_at, "data": e.data}
                    for e in workflow.history(ctx, entity_type, entity_id)],
    }


@router.post("/workflows/{entity_type}/{entity_id}/transitions")
def do_transition(entity_type: str, entity_id: uuid.UUID, body: TransitionIn, ctx: TenantContext = Depends(require())):
    ent = workflow.entity(entity_type)
    record = ent.load(ctx, entity_id, for_update=True)
    result = workflow.transition(ctx, entity_type, record, entity_id, body.transition.strip().upper(), body.comment)
    ctx.db.commit()
    return result


@router.post("/workflows/escalations/run")
def run_escalations(ctx: TenantContext = Depends(require(P.CONFIG_MANAGE))):
    return {"escalations": workflow.escalate_due(ctx.db, organization_id=ctx.organization_id)}
