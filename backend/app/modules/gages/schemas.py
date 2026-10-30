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


class _GageFields(BaseModel):
    description: str | None = Field(default=None, min_length=2, max_length=300)
    gage_type_id: uuid.UUID | None = None
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    range_min: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    range_max: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, max_length=20)
    resolution: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    accuracy: str | None = Field(default=None, max_length=120)
    criticality: Criticality | None = None
    location: str | None = Field(default=None, max_length=200)
    responsible_user_id: uuid.UUID | None = None
    calibration_frequency_days: int | None = Field(default=None, ge=1, le=3650)
    last_calibration_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _range_order(self):
        if self.range_min is not None and self.range_max is not None and self.range_min > self.range_max:
            raise ValueError("range_min must be less than or equal to range_max")
        return self


class GageCreate(_GageFields):
    gage_code: str = Field(min_length=1, max_length=50, pattern=GAGE_CODE_PATTERN)
    description: str = Field(min_length=2, max_length=300)
    gage_type_id: uuid.UUID
    plant_id: uuid.UUID


class GageUpdate(_GageFields):
    """Partial update. The Gage ID and the controlled status cannot be changed here."""

    model_config = ConfigDict(extra="forbid")


class GageTransitionIn(BaseModel):
    target: ControlStatus
    reason: str = Field(min_length=3, max_length=1000)
    # Only when releasing from IN_CALIBRATION. Interim until Calibration Management (phase 3)
    # records calibrations as activities with evidence.
    calibration_date: date | None = None


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
    calibration_frequency_days: int
    last_calibration_date: date | None
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
