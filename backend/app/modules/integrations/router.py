import json
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.errors import BusinessRuleError
from app.modules.documents import service as documents
from app.modules.events import service as events
from app.modules.events.models import EVENT_TYPES
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.integrations import api_clients, connectors, exchange, imports, webhooks
from app.modules.oot import service as oot

router = APIRouter(tags=["integrations"])
documents.register("import_job", P.INTEGRATIONS_READ, P.INTEGRATIONS_MANAGE,
                   lambda ctx, i: imports.get_job(ctx, i))
oot.impact_sources.append(connectors.device_impact)


# ---------------------------------------------------------------- API clients

class ApiClientIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    role_code: str
    plant_ids: list[uuid.UUID] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    user_id: uuid.UUID
    key_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None


class ApiClientCreated(ApiClientOut):
    api_key: str


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/integrations/api-clients", response_model=list[ApiClientOut])
def list_clients(ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return api_clients.list_clients(ctx)


@router.post("/integrations/api-clients", response_model=ApiClientCreated, status_code=201)
def create_client(body: ApiClientIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE, P.USERS_MANAGE))):
    client, raw = api_clients.create(ctx, body.name, body.role_code, body.plant_ids, body.expires_at)
    return ApiClientCreated(**ApiClientOut.model_validate(client).model_dump(), api_key=raw)


@router.post("/integrations/api-clients/{client_id}/revoke", response_model=ApiClientOut)
def revoke_client(client_id: uuid.UUID, body: ReasonIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return api_clients.revoke(ctx, client_id, body.reason)


@router.get("/integrations/api-clients/{client_id}/activity")
def client_activity(client_id: uuid.UUID, limit: int = Query(default=100, ge=1, le=1000),
                    ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return [{"method": r.method, "path": r.path, "request_id": r.request_id, "ip_address": r.ip_address,
             "requested_at": r.requested_at} for r in api_clients.activity(ctx, client_id, limit)]


# ---------------------------------------------------------------- events and webhooks

class WebhookIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    url: str = Field(min_length=8, max_length=500)
    event_types: list[str] = Field(min_length=1)


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str


@router.get("/integrations/event-types")
def event_types(_: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return list(EVENT_TYPES)


@router.get("/integrations/events")
def list_events(event_type: str | None = None, limit: int = Query(default=100, ge=1, le=500),
                ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return [{"id": e.id, "event_type": e.event_type, "entity_type": e.entity_type, "entity_id": e.entity_id,
             "payload": e.payload, "created_at": e.created_at}
            for e in events.list_events(ctx.db, ctx.organization_id, event_type, limit)]


@router.get("/integrations/webhooks", response_model=list[WebhookOut])
def list_webhooks(ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return webhooks.list_endpoints(ctx)


@router.post("/integrations/webhooks", response_model=WebhookCreated, status_code=201)
def create_webhook(body: WebhookIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    ep, secret = webhooks.create_endpoint(ctx, body.name, body.url, body.event_types)
    return WebhookCreated(**WebhookOut.model_validate(ep).model_dump(), secret=secret)


@router.post("/integrations/webhooks/{endpoint_id}/activate", response_model=WebhookOut)
def activate_webhook(endpoint_id: uuid.UUID, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return webhooks.set_active(ctx, endpoint_id, True)


@router.post("/integrations/webhooks/{endpoint_id}/deactivate", response_model=WebhookOut)
def deactivate_webhook(endpoint_id: uuid.UUID, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return webhooks.set_active(ctx, endpoint_id, False)


@router.get("/integrations/webhook-deliveries")
def list_deliveries(endpoint_id: uuid.UUID | None = None, status: str | None = None,
                    limit: int = Query(default=100, ge=1, le=500),
                    ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return [{"id": d.id, "endpoint_id": d.endpoint_id, "event_id": d.event_id, "event_type": etype,
             "entity_id": eid, "status": d.status, "attempts": d.attempts, "next_attempt_at": d.next_attempt_at,
             "last_status_code": d.last_status_code, "last_error": d.last_error, "delivered_at": d.delivered_at,
             "created_at": d.created_at} for d, etype, eid in webhooks.deliveries(ctx, endpoint_id, status, limit)]


@router.get("/integrations/webhook-deliveries/{delivery_id}/attempts")
def delivery_attempts(delivery_id: uuid.UUID, ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return [{"attempt": a.attempt, "status_code": a.status_code, "error": a.error, "duration_ms": a.duration_ms,
             "attempted_at": a.attempted_at} for a in webhooks.attempts(ctx, delivery_id)]


@router.post("/integrations/webhook-deliveries/{delivery_id}/retry")
def retry_delivery(delivery_id: uuid.UUID, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    d = webhooks.retry(ctx, delivery_id)
    return {"id": d.id, "status": d.status}


@router.post("/integrations/webhooks/dispatch")
def dispatch_now(ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    """Run fan-out and delivery now for this organization (the scheduler does it periodically)."""
    queued = webhooks.enqueue(ctx.db, ctx.organization_id)
    return {"queued": queued, **webhooks.dispatch(ctx.db, organization_id=ctx.organization_id)}


# ---------------------------------------------------------------- imports

class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    importer: str
    target_id: uuid.UUID | None
    filename: str
    attachment_id: uuid.UUID
    mapping: dict
    status: str
    total_rows: int
    valid_rows: int
    error_count: int
    errors: list
    preview: list
    summary: dict | None
    reprocess_of_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    committed_by: uuid.UUID | None
    committed_at: datetime | None


class MappingIn(BaseModel):
    mapping: dict[str, str]


@router.get("/integrations/importers")
def list_importers(ctx: TenantContext = Depends(require())):
    return [{"code": i.code, "label": i.label, "permission": i.permission, "target": i.target_label,
             "allowed": ctx.has(i.permission),
             "fields": [{"name": f.name, "required": f.required, "aliases": list(f.aliases)} for f in i.fields]}
            for i in imports.IMPORTERS.values()]


@router.get("/integrations/importers/{code}/template")
def importer_template(code: str, ctx: TenantContext = Depends(require())):
    ctx.ensure(imports.importer(code).permission)
    return Response(imports.template(code),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{code}-template.xlsx"'})


@router.post("/integrations/imports", response_model=ImportJobOut, status_code=201)
async def create_import(importer: str = Form(...), target_id: uuid.UUID | None = Form(default=None),
                        mapping: str | None = Form(default=None), file: UploadFile = File(...),
                        ctx: TenantContext = Depends(require())):
    data = await file.read()
    parsed = None
    if mapping:
        try:
            parsed = json.loads(mapping)
            assert isinstance(parsed, dict) and all(isinstance(v, str) for v in parsed.values())
        except (ValueError, AssertionError):
            raise BusinessRuleError("mapping must be a JSON object {field: column}", code="invalid_mapping")
    return imports.create_job(ctx, importer, file.filename or "import.csv", data, parsed, target_id)


@router.get("/integrations/imports", response_model=list[ImportJobOut])
def list_imports(importer: str | None = None, target_id: uuid.UUID | None = None,
                 ctx: TenantContext = Depends(require())):
    jobs = imports.list_jobs(ctx, importer, target_id)
    return [j for j in jobs if ctx.has(imports.IMPORTERS[j.importer].permission) or ctx.has(P.INTEGRATIONS_READ)]


@router.get("/integrations/imports/{job_id}", response_model=ImportJobOut)
def get_import(job_id: uuid.UUID, ctx: TenantContext = Depends(require())):
    job = imports.get_job(ctx, job_id)
    if not ctx.has(P.INTEGRATIONS_READ):
        ctx.ensure(imports.importer(job.importer).permission)
    return job


@router.post("/integrations/imports/{job_id}/commit", response_model=ImportJobOut)
def commit_import(job_id: uuid.UUID, ctx: TenantContext = Depends(require())):
    return imports.commit_job(ctx, job_id)


@router.post("/integrations/imports/{job_id}/reprocess", response_model=ImportJobOut, status_code=201)
def reprocess_import(job_id: uuid.UUID, body: MappingIn, ctx: TenantContext = Depends(require())):
    return imports.reprocess(ctx, job_id, body.mapping)


# ---------------------------------------------------------------- devices and connectors

class DeviceIn(BaseModel):
    device_code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=2, max_length=120)
    adapter: str
    plant_id: uuid.UUID
    serial_number: str | None = Field(default=None, max_length=80)
    gage_id: uuid.UUID | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_code: str
    name: str
    adapter: str
    plant_id: uuid.UUID
    serial_number: str | None
    gage_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class LinkIn(BaseModel):
    gage_id: uuid.UUID | None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reading_uid: str
    value: Decimal
    unit: str | None
    raw: str
    gage_id: uuid.UUID | None
    gage_status: str | None
    captured_at: datetime
    received_at: datetime

    @field_serializer("value")
    def _ser(self, v):
        return format(v.normalize(), "f")


class FrameIn(BaseModel):
    reading_uid: str = Field(min_length=1, max_length=80)
    raw: str = Field(min_length=1, max_length=500)
    captured_at: datetime | None = None


class SubmitIn(BaseModel):
    device_code: str = Field(min_length=2, max_length=40)
    readings: list[FrameIn] = Field(min_length=1, max_length=1000)


class SimulateIn(BaseModel):
    nominal: float
    sigma: float = Field(ge=0, le=1e6)
    count: int = Field(default=10, ge=1, le=200)
    unit: str = Field(default="mm", max_length=10)


@router.get("/integrations/adapters")
def adapters(_: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return {"adapters": connectors.catalogue(), "planned_not_supported": connectors.PLANNED}


@router.get("/integrations/devices", response_model=list[DeviceOut])
def list_devices(ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return connectors.list_devices(ctx)


@router.post("/integrations/devices", response_model=DeviceOut, status_code=201)
def create_device(body: DeviceIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return connectors.create_device(ctx, body.model_dump())


@router.put("/integrations/devices/{device_id}/gage", response_model=DeviceOut)
def link_device(device_id: uuid.UUID, body: LinkIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return connectors.link_gage(ctx, device_id, body.gage_id)


@router.get("/integrations/devices/{device_id}/readings", response_model=list[ReadingOut])
def device_readings(device_id: uuid.UUID, limit: int = Query(default=100, ge=1, le=1000),
                    ctx: TenantContext = Depends(require(P.INTEGRATIONS_READ))):
    return connectors.readings(ctx, device_id, limit)


@router.post("/integrations/devices/{device_id}/simulate")
def simulate(device_id: uuid.UUID, body: SimulateIn, ctx: TenantContext = Depends(require(P.INTEGRATIONS_MANAGE))):
    return connectors.simulate(ctx, device_id, body.nominal, body.sigma, body.count, body.unit)


@router.post("/connectors/readings")
def submit_readings(body: SubmitIn, ctx: TenantContext = Depends(require(P.CONNECTORS_SUBMIT))):
    return connectors.submit(ctx, body.device_code, [r.model_dump() for r in body.readings])


# ---------------------------------------------------------------- exchange (read contracts v1)

@router.get("/exchange/{resource}")
def exchange_page(resource: str, response: Response, page: int = Query(default=1, ge=1),
                  page_size: int = Query(default=100, ge=1, le=500), updated_since: datetime | None = None,
                  status: str | None = None, gage_id: uuid.UUID | None = None,
                  ctx: TenantContext = Depends(require())):
    response.headers["X-Contract-Version"] = exchange.CONTRACT_VERSION
    return exchange.page(ctx, resource, page_no=page, page_size=page_size, updated_since=updated_since,
                         status=status, gage_id=gage_id)
