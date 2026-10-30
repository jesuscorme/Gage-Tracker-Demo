"""Device connector architecture.

``Adapter`` turns the raw output of an instrument (a line of text, a frame) into a
``Reading``. Adapters run inside the Edge Connector (edge/edge_agent.py) next to the
instruments, and the server re-parses the raw frame it receives with the same adapter
before storing it, so a reading is only accepted if its raw evidence parses to it.

Only adapters listed here with status TESTED are claimed to work, and only for the
protocol they implement. No manufacturer-specific protocol is implemented yet: the
generic adapter accepts a documented ASCII line format, and the simulator produces
frames in that format to exercise the whole flow end to end.
"""

import random
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.gages import service as gages
from app.modules.gages.status import GageStatus
from app.modules.identity.deps import TenantContext
from app.modules.integrations.models import Device, DeviceReading
from app.modules.organizations.router import get_plant


@dataclass(frozen=True)
class Reading:
    value: Decimal
    unit: str | None


class Adapter:
    code = ""
    name = ""
    status = "EXPERIMENTAL"          # TESTED = covered by automated tests with real frames of its protocol
    device_kinds: tuple[str, ...] = ()
    description = ""

    def parse(self, raw: str) -> Reading:
        raise NotImplementedError


class GenericAsciiAdapter(Adapter):
    """One reading per line: ``<value>[ <unit>]`` with optional sign, '.' or ',' decimal mark.

    Examples: ``12.345 mm``, ``-0,002mm``, ``+25.40 in``, ``45.2 N.m``. This is the format
    produced by many instruments configured for plain ASCII output and by keyboard-wedge
    style interfaces, but compatibility with a given model must be verified on site.
    """

    code = "generic_ascii"
    name = "Generic ASCII line (value + unit)"
    status = "TESTED"
    device_kinds = ("digital caliper", "digital micrometer", "dial/digital indicator", "torque tester",
                    "other dimensional")
    _re = re.compile(r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*([A-Za-zµ°][A-Za-z0-9.µ°/]{0,9})?\s*$")

    def parse(self, raw: str) -> Reading:
        m = self._re.match(raw.replace("\r", "").replace("\n", ""))
        if not m:
            raise ValueError(f"unrecognised frame: {raw[:40]!r}")
        try:
            value = Decimal(m.group(1).replace(",", "."))
        except InvalidOperation:
            raise ValueError("invalid number")
        return Reading(value=value, unit=m.group(2))


class SimulatorAdapter(GenericAsciiAdapter):
    """Software device used to validate the flow without hardware (frames in generic ASCII)."""

    code = "simulator"
    name = "Device simulator (testing only)"
    status = "TESTED"
    device_kinds = ("simulated",)

    @staticmethod
    def frames(nominal: float, sigma: float, n: int, unit: str, seed: int, decimals: int = 4) -> list[str]:
        rng = random.Random(seed)
        return [f"{rng.gauss(nominal, sigma):.{decimals}f} {unit}" for _ in range(n)]


ADAPTERS: dict[str, Adapter] = {a.code: a for a in (GenericAsciiAdapter(), SimulatorAdapter())}
# Planned (architecture ready, no adapter yet): never presented as supported.
PLANNED = ["Mitutoyo Digimatic (via USB-ITN / U-WAVE)", "Sylvac Bluetooth / Opto RS232", "CMM result files (DMIS, "
           "PC-DMIS CSV export)", "Optical comparator QC controllers", "Torque analysers (serial/USB)"]


def catalogue() -> list[dict]:
    return [{"code": a.code, "name": a.name, "status": a.status, "device_kinds": list(a.device_kinds),
             "description": " ".join(a.__doc__.split()) if a.__doc__ else ""} for a in ADAPTERS.values()]


# ---------------------------------------------------------------- devices

def get_device(ctx: TenantContext, device_id: uuid.UUID) -> Device:
    d = ctx.db.scalar(select(Device).where(Device.id == device_id, Device.organization_id == ctx.organization_id))
    if d is None or not ctx.can_access_plant(d.plant_id):
        raise NotFoundError("Device not found")
    return d


def list_devices(ctx: TenantContext) -> list[Device]:
    stmt = select(Device).where(Device.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(Device.plant_id.in_(ctx.plant_ids))
    return list(ctx.db.scalars(stmt.order_by(Device.device_code)))


def create_device(ctx: TenantContext, data: dict) -> Device:
    if data["adapter"] not in ADAPTERS:
        raise BusinessRuleError("Unknown adapter", code="invalid_adapter", details=list(ADAPTERS))
    get_plant(ctx, data["plant_id"])
    if data.get("gage_id"):
        gages.get_gage(ctx, data["gage_id"])
    code = data["device_code"].strip().upper()
    if ctx.db.scalar(select(Device.id).where(Device.organization_id == ctx.organization_id,
                                             Device.device_code == code)):
        raise ConflictError("Device code already exists", code="duplicate_device")
    d = Device(organization_id=ctx.organization_id, created_by=ctx.user_id, **(data | {"device_code": code}))
    ctx.db.add(d)
    ctx.db.flush()
    ctx.audit(action="device.registered", entity_type="device", entity_id=d.id,
              changes={"device_code": code, "adapter": d.adapter, "gage_id": str(d.gage_id) if d.gage_id else None})
    ctx.db.commit()
    return d


def link_gage(ctx: TenantContext, device_id: uuid.UUID, gage_id: uuid.UUID | None) -> Device:
    d = get_device(ctx, device_id)
    if gage_id:
        gages.get_gage(ctx, gage_id)
    before = d.gage_id
    d.gage_id = gage_id
    ctx.audit(action="device.gage_linked", entity_type="device", entity_id=d.id,
              changes={"gage_id": [str(before) if before else None, str(gage_id) if gage_id else None]})
    ctx.db.commit()
    return d


# ---------------------------------------------------------------- readings

def submit(ctx: TenantContext, device_code: str, frames: list[dict]) -> dict:
    """Accept readings from an edge agent. Idempotent per (device, reading_uid)."""
    d = ctx.db.scalar(select(Device).where(Device.organization_id == ctx.organization_id,
                                           Device.device_code == device_code.strip().upper()))
    if d is None or not ctx.can_access_plant(d.plant_id):
        raise NotFoundError("Device not found")
    if not d.is_active:
        raise ConflictError("Device is inactive", code="device_inactive")
    adapter = ADAPTERS[d.adapter]
    gage = gages.get_gage(ctx, d.gage_id) if d.gage_id else None
    status = gages.current_status(ctx, gage).value if gage else None
    accepted, duplicates, rejected = 0, 0, []
    uids = [f["reading_uid"] for f in frames]
    if len(set(uids)) != len(uids):
        raise BusinessRuleError("reading_uid values must be unique within a batch", code="duplicate_reading_uid")
    existing = set(ctx.db.scalars(select(DeviceReading.reading_uid).where(
        DeviceReading.device_id == d.id, DeviceReading.reading_uid.in_(uids))))
    now = datetime.now(UTC)
    for i, f in enumerate(frames, start=1):
        if f["reading_uid"] in existing:
            duplicates += 1
            continue
        try:
            reading = adapter.parse(f["raw"])
        except ValueError as exc:
            rejected.append({"index": i, "reading_uid": f["reading_uid"], "error": str(exc)})
            continue
        captured = f.get("captured_at") or now
        if captured > now + timedelta(minutes=5):
            rejected.append({"index": i, "reading_uid": f["reading_uid"], "error": "captured_at is in the future"})
            continue
        ctx.db.add(DeviceReading(organization_id=ctx.organization_id, device_id=d.id,
                                 gage_id=gage.id if gage else None, reading_uid=f["reading_uid"],
                                 value=reading.value, unit=reading.unit, raw=f["raw"][:500], gage_status=status,
                                 captured_at=captured, submitted_by=ctx.user_id))
        accepted += 1
    ctx.audit(action="device.readings_received", entity_type="device", entity_id=d.id,
              changes={"accepted": accepted, "duplicates": duplicates, "rejected": len(rejected),
                       "gage_status": status})
    ctx.db.commit()
    warnings = []
    if gage and GageStatus(status) in (GageStatus.OUT_OF_SERVICE, GageStatus.OVERDUE, GageStatus.INACTIVE):
        warnings.append(f"Gage {gage.gage_code} is {status}: readings were stored with that status for traceability "
                        "and cannot be used as valid measurements")
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected, "warnings": warnings}


def readings(ctx: TenantContext, device_id: uuid.UUID, limit: int) -> list[DeviceReading]:
    d = get_device(ctx, device_id)
    return list(ctx.db.scalars(select(DeviceReading).where(DeviceReading.device_id == d.id)
                               .order_by(DeviceReading.captured_at.desc()).limit(limit)))


def simulate(ctx: TenantContext, device_id: uuid.UUID, nominal: float, sigma: float, n: int, unit: str) -> dict:
    """Generate frames with the simulator and push them through the normal submission path."""
    d = get_device(ctx, device_id)
    if d.adapter != "simulator":
        raise BusinessRuleError("Only simulator devices can generate readings", code="not_a_simulator")
    seed = int(ctx.db.scalar(select(func.count(DeviceReading.id)).where(DeviceReading.device_id == d.id)) or 0)
    frames = SimulatorAdapter.frames(nominal, sigma, n, unit, seed=d.id.int % 10_000 + seed)
    batch = [{"reading_uid": f"sim-{uuid.uuid4().hex[:12]}", "raw": raw} for raw in frames]
    return submit(ctx, d.device_code, batch)


def device_impact(ctx: TenantContext, case, start_dt, end_dt) -> list[dict]:
    """OOT impact source: readings taken with the gage during the affected period."""
    rows = ctx.db.execute(select(Device.id, Device.device_code, func.count(DeviceReading.id),
                                 func.min(DeviceReading.captured_at), func.max(DeviceReading.captured_at))
                          .join(DeviceReading, DeviceReading.device_id == Device.id)
                          .where(DeviceReading.gage_id == case.gage_id, DeviceReading.captured_at >= start_dt,
                                 DeviceReading.captured_at < end_dt)
                          .group_by(Device.id, Device.device_code)).all()
    return [{"item_type": "DEVICE_READINGS", "ref_id": dev_id, "ref_code": code,
             "description": f"{n} readings captured through device {code} between {first:%Y-%m-%d} and {last:%Y-%m-%d}",
             "occurred_at": last, "data": {"readings": n}} for dev_id, code, n, first, last in rows]
