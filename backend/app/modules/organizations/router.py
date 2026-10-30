import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.audit import service as audit
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.organizations.models import Department, Organization, Plant

router = APIRouter(tags=["organization"])


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    due_soon_days: int
    timezone: str


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    due_soon_days: int | None = Field(default=None, ge=0, le=365)
    timezone: str | None = Field(default=None, max_length=64)


class PlantIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    is_active: bool | None = None


class PlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class DepartmentIn(BaseModel):
    plant_id: uuid.UUID
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    is_active: bool | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    plant_id: uuid.UUID
    code: str
    name: str
    is_active: bool


ORG_FIELDS = ["name", "due_soon_days", "timezone"]


@router.get("/organization", response_model=OrganizationOut)
def get_organization(ctx: TenantContext = Depends(require(P.ORG_READ))):
    return ctx.organization


@router.patch("/organization", response_model=OrganizationOut)
def update_organization(body: OrganizationUpdate, ctx: TenantContext = Depends(require(P.ORG_MANAGE))):
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    if "timezone" in data:
        try:
            ZoneInfo(data["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise BusinessRuleError("Unknown time zone", code="invalid_timezone")
    org: Organization = ctx.organization
    before = audit.snapshot(org, ORG_FIELDS)
    for k, v in data.items():
        setattr(org, k, v)
    changes = audit.diff(before, audit.snapshot(org, ORG_FIELDS))
    if changes:
        ctx.audit(action="organization.updated", entity_type="organization", entity_id=org.id, changes=changes)
    ctx.db.commit()
    return org


# ---------------------------------------------------------------- plants


def get_plant(ctx: TenantContext, plant_id: uuid.UUID) -> Plant:
    """Plant of the current tenant that the user may access, or 404."""
    plant = ctx.db.scalar(
        select(Plant).where(Plant.id == plant_id, Plant.organization_id == ctx.organization_id)
    )
    if plant is None or not ctx.can_access_plant(plant.id):
        raise NotFoundError("Plant not found")
    return plant


@router.get("/plants", response_model=list[PlantOut])
def list_plants(ctx: TenantContext = Depends(require(P.ORG_READ))):
    stmt = select(Plant).where(Plant.organization_id == ctx.organization_id).order_by(Plant.code)
    if ctx.plant_ids is not None:
        stmt = stmt.where(Plant.id.in_(ctx.plant_ids))
    return list(ctx.db.scalars(stmt))


@router.post("/plants", response_model=PlantOut, status_code=201)
def create_plant(body: PlantIn, ctx: TenantContext = Depends(require(P.PLANTS_MANAGE))):
    code = body.code.strip().upper()
    if ctx.db.scalar(select(Plant.id).where(Plant.organization_id == ctx.organization_id, Plant.code == code)):
        raise ConflictError("A plant with this code already exists", code="duplicate_plant_code")
    plant = Plant(organization_id=ctx.organization_id, code=code, name=body.name.strip())
    ctx.db.add(plant)
    ctx.db.flush()
    ctx.audit(action="plant.created", entity_type="plant", entity_id=plant.id,
              changes={"code": code, "name": plant.name})
    ctx.db.commit()
    return plant


@router.patch("/plants/{plant_id}", response_model=PlantOut)
def update_plant(plant_id: uuid.UUID, body: PlantUpdate, ctx: TenantContext = Depends(require(P.PLANTS_MANAGE))):
    plant = get_plant(ctx, plant_id)
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    before = audit.snapshot(plant, list(data))
    for k, v in data.items():
        setattr(plant, k, v)
    changes = audit.diff(before, data)
    if changes:
        ctx.audit(action="plant.updated", entity_type="plant", entity_id=plant.id, changes=changes)
    ctx.db.commit()
    return plant


# ---------------------------------------------------------------- departments


def get_department(ctx: TenantContext, department_id: uuid.UUID) -> Department:
    dept = ctx.db.scalar(
        select(Department).where(
            Department.id == department_id, Department.organization_id == ctx.organization_id
        )
    )
    if dept is None or not ctx.can_access_plant(dept.plant_id):
        raise NotFoundError("Department not found")
    return dept


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(plant_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require(P.ORG_READ))):
    stmt = select(Department).where(Department.organization_id == ctx.organization_id)
    if plant_id is not None:
        stmt = stmt.where(Department.plant_id == plant_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(Department.plant_id.in_(ctx.plant_ids))
    return list(ctx.db.scalars(stmt.order_by(Department.code)))


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentIn, ctx: TenantContext = Depends(require(P.PLANTS_MANAGE))):
    plant = get_plant(ctx, body.plant_id)
    code = body.code.strip().upper()
    if ctx.db.scalar(select(Department.id).where(Department.plant_id == plant.id, Department.code == code)):
        raise ConflictError("A department with this code already exists in the plant",
                            code="duplicate_department_code")
    dept = Department(organization_id=ctx.organization_id, plant_id=plant.id, code=code, name=body.name.strip())
    ctx.db.add(dept)
    ctx.db.flush()
    ctx.audit(action="department.created", entity_type="department", entity_id=dept.id,
              changes={"plant": plant.code, "code": code, "name": dept.name})
    ctx.db.commit()
    return dept


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: uuid.UUID, body: DepartmentUpdate, ctx: TenantContext = Depends(require(P.PLANTS_MANAGE))
):
    dept = get_department(ctx, department_id)
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    before = audit.snapshot(dept, list(data))
    for k, v in data.items():
        setattr(dept, k, v)
    changes = audit.diff(before, data)
    if changes:
        ctx.audit(action="department.updated", entity_type="department", entity_id=dept.id, changes=changes)
    ctx.db.commit()
    return dept
