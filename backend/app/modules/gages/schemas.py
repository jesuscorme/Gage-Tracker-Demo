import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.modules.gages.status import ControlStatus, GageStatus

Criticality = Literal["LOW", "MEDIUM", "HIGH"]
GAGE_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"


# ---------------------------------------------------------------- gage types


class GageTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    default_frequency_days: int | None = Field(default=None, ge=1, le=3650)


class GageTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    default_frequency_days: int | None = Field(default=None, ge=1, le=3650)
    is_active: bool | None = None


class GageTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    default_frequency_days: int | None
    is_active: bool


# ---------------------------------------------------------------- gages


class _Descriptive(BaseModel):
    description: str | None = Field(default=None, min_length=2, max_length=300)
    gage_type_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    range_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    range_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, max_length=20)
    resolution: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    accuracy: str | None = Field(default=None, max_length=120)
    criticality: Criticality | None = None
    calibration_frequency_days: int | None = Field(default=None, ge=1, le=3650)
    acquisition_date: date | None = None
    in_service_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _range_order(self):
        if self.range_min is not None and self.range_max is not None and self.range_min > self.range_max:
            raise ValueError("range_min must be less than or equal to range_max")
        if self.acquisition_date and self.in_service_date and self.in_service_date < self.acquisition_date:
            raise ValueError("in_service_date cannot be earlier than acquisition_date")
        return self


class GageCreate(_Descriptive):
    gage_code: str = Field(min_length=1, max_length=50, pattern=GAGE_CODE_PATTERN)
    description: str = Field(min_length=2, max_length=300)
    gage_type_id: uuid.UUID
    plant_id: uuid.UUID
    department_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=200)
    responsible_user_id: uuid.UUID | None = None
    # Initial record of the last calibration (legacy inventory). After registration the
    # date only changes through a released calibration activity.
    last_calibration_date: date | None = None


class GageUpdate(_Descriptive):
    """Descriptive data only. Gage ID, status, assignment and calibration dates are
    changed through their own controlled operations."""

    model_config = ConfigDict(extra="forbid")


class GageTransferIn(BaseModel):
    """Reassignment of responsible and/or transfer to another plant, department or location."""

    model_config = ConfigDict(extra="forbid")
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=200)
    responsible_user_id: uuid.UUID | None = None
    reason: str = Field(min_length=3, max_length=1000)


class GageTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: ControlStatus
    reason: str = Field(min_length=3, max_length=1000)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    changes: dict
    reason: str
    moved_by: uuid.UUID
    moved_by_name: str | None = None
    moved_at: datetime


class ImportRowError(BaseModel):
    row: int
    gage_code: str | None
    errors: list[str]


class ImportResult(BaseModel):
    dry_run: bool
    total_rows: int
    valid_rows: int
    created: int
    errors: list[ImportRowError]


class Ref(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str


class GageOut(BaseModel):
    id: uuid.UUID
    gage_code: str
    description: str
    gage_type: Ref
    plant: Ref
    department: Ref | None
    responsible: UserRef | None
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    range_min: Decimal | None
    range_max: Decimal | None
    unit: str | None
    resolution: Decimal | None
    accuracy: str | None
    criticality: str | None
    location: str | None
    notes: str | None
    acquisition_date: date | None
    in_service_date: date | None
    calibration_frequency_days: int
    last_calibration_date: date | None
    last_verification_date: date | None
    next_due_date: date | None
    days_to_due: int | None
    control_status: ControlStatus
    status: GageStatus
    available_for_use: bool
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("range_min", "range_max", "resolution")
    def _decimal(self, v: Decimal | None) -> str | None:
        # Same representation whether the value comes from the request or the database.
        return None if v is None else format(v.normalize(), "f")


class GagePage(BaseModel):
    items: list[GageOut]
    total: int
    page: int
    page_size: int


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_control_status: str | None
    to_control_status: str
    from_status: str | None
    to_status: str
    reason: str | None
    changed_by: uuid.UUID | None
    changed_by_name: str | None = None
    changed_at: datetime
