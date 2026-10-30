"""Inventory import (CSV / Excel) and export.

Import is all-or-nothing: every row is validated with the same rules as the API; if
any row fails, nothing is saved and the errors are reported per row. ``dry_run``
validates without saving.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook, load_workbook
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import AppError, BusinessRuleError
from app.modules.gages import service
from app.modules.gages.models import Gage, GageType
from app.modules.gages.schemas import GageCreate, ImportResult, ImportRowError
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import OrganizationMembership, User
from app.modules.organizations.models import Department, Plant

MAX_ROWS = 5000

# Template columns. Codes/e-mails are used instead of internal ids.
COLUMNS = [
    "gage_code", "description", "gage_type_code", "plant_code", "department_code", "location",
    "responsible_email", "manufacturer", "model", "serial_number", "range_min", "range_max", "unit",
    "resolution", "accuracy", "criticality", "calibration_frequency_days", "last_calibration_date",
    "acquisition_date", "in_service_date", "notes",
]
REQUIRED = ["gage_code", "description", "gage_type_code", "plant_code"]


def _cell(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def parse_file(filename: str, data: bytes) -> list[dict[str, str | None]]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise BusinessRuleError("The Excel file could not be read", code="invalid_file")
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
        if not rows:
            return []
        header = [(_cell(h) or "").lower() for h in rows[0]]
        body = [[_cell(v) for v in r] for r in rows[1:]]
    elif name.endswith(".csv"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise BusinessRuleError("CSV must be UTF-8 encoded", code="invalid_encoding")
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t") if text.strip() else csv.excel
        reader = list(csv.reader(io.StringIO(text), dialect))
        if not reader:
            return []
        header = [h.strip().lower() for h in reader[0]]
        body = [[_cell(v) for v in r] for r in reader[1:]]
    else:
        raise BusinessRuleError("Use a .csv or .xlsx file", code="invalid_file_type")

    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise BusinessRuleError("Missing required columns", code="missing_columns", details=missing)
    out = []
    for r in body:
        if not any(r):
            continue
        out.append({h: (r[i] if i < len(r) else None) for i, h in enumerate(header) if h in COLUMNS})
    if len(out) > MAX_ROWS:
        raise BusinessRuleError(f"At most {MAX_ROWS} rows per import", code="too_many_rows")
    return out


def _lookups(ctx: TenantContext):
    db = ctx.db
    types = {t.code: t.id for t in db.scalars(select(GageType).where(GageType.organization_id == ctx.organization_id))}
    plants = {p.code: p.id for p in db.scalars(select(Plant).where(Plant.organization_id == ctx.organization_id))}
    depts = {(d.plant_id, d.code): d.id
             for d in db.scalars(select(Department).where(Department.organization_id == ctx.organization_id))}
    users = dict(db.execute(
        select(User.email, User.id).join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(OrganizationMembership.organization_id == ctx.organization_id)
    ).all())
    return types, plants, depts, users


def _to_payload(row: dict, lookups) -> tuple[dict, list[str]]:
    types, plants, depts, users = lookups
    errors: list[str] = []
    payload: dict = {k: row.get(k) for k in (
        "gage_code", "description", "location", "manufacturer", "model", "serial_number", "range_min",
        "range_max", "unit", "resolution", "accuracy", "calibration_frequency_days",
        "last_calibration_date", "acquisition_date", "in_service_date", "notes")}
    payload["criticality"] = (row.get("criticality") or "").upper() or None

    tcode = (row.get("gage_type_code") or "").upper()
    payload["gage_type_id"] = types.get(tcode)
    if tcode and not payload["gage_type_id"]:
        errors.append(f"gage_type_code '{tcode}' does not exist")
    pcode = (row.get("plant_code") or "").upper()
    payload["plant_id"] = plants.get(pcode)
    if pcode and not payload["plant_id"]:
        errors.append(f"plant_code '{pcode}' does not exist")
    dcode = (row.get("department_code") or "").upper()
    if dcode:
        payload["department_id"] = depts.get((payload["plant_id"], dcode))
        if not payload["department_id"]:
            errors.append(f"department_code '{dcode}' does not exist in plant '{pcode}'")
    email = (row.get("responsible_email") or "").lower()
    if email:
        payload["responsible_user_id"] = users.get(email)
        if not payload["responsible_user_id"]:
            errors.append(f"responsible_email '{email}' is not a member of the organization")
    return {k: v for k, v in payload.items() if v is not None}, errors


def import_gages(ctx: TenantContext, filename: str, data: bytes, dry_run: bool) -> ImportResult:
    rows = parse_file(filename, data)
    lookups = _lookups(ctx)
    errors: list[ImportRowError] = []
    created = 0
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        payload, row_errors = _to_payload(row, lookups)
        if not row_errors:
            try:
                body = GageCreate(**payload)
                with ctx.db.begin_nested():
                    service.build_gage(ctx, body)
                created += 1
            except ValidationError as exc:
                row_errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            except AppError as exc:
                row_errors = [exc.message]
        if row_errors:
            errors.append(ImportRowError(row=i, gage_code=row.get("gage_code"), errors=row_errors))

    result = ImportResult(dry_run=dry_run, total_rows=len(rows), valid_rows=created, created=0, errors=errors)
    if errors or dry_run or not rows:
        ctx.db.rollback()
        return result
    ctx.audit(action="gage.imported", entity_type="gage_import", entity_id=None,
              changes={"filename": filename, "rows": len(rows), "created": created})
    ctx.db.commit()
    result.created = created
    return result


def template_csv() -> bytes:
    return ("﻿" + ",".join(COLUMNS) + "\n").encode("utf-8")


EXPORT_COLUMNS = [
    ("Gage ID", "gage_code"), ("Description", "description"), ("Type", "type"), ("Plant", "plant"),
    ("Department", "department"), ("Location", "location"), ("Responsible", "responsible"),
    ("Manufacturer", "manufacturer"), ("Model", "model"), ("Serial number", "serial_number"),
    ("Range min", "range_min"), ("Range max", "range_max"), ("Unit", "unit"), ("Resolution", "resolution"),
    ("Accuracy", "accuracy"), ("Criticality", "criticality"), ("Frequency (days)", "calibration_frequency_days"),
    ("Last calibration", "last_calibration_date"), ("Next due", "next_due_date"),
    ("Last verification", "last_verification_date"), ("Acquisition date", "acquisition_date"),
    ("In-service date", "in_service_date"), ("Status", "status"), ("Available for use", "available"),
]


def _export_rows(ctx: TenantContext, gages: list[Gage]):
    for g in gages:
        out = service.to_out(ctx, g)
        values = out.model_dump()
        values.update(
            type=g.gage_type.name, plant=g.plant.code, department=g.department.code if g.department else None,
            responsible=g.responsible.full_name if g.responsible else None,
            available="yes" if out.available_for_use else "no", status=out.status.value,
        )
        yield [values.get(key) for _, key in EXPORT_COLUMNS]


def _fmt(v):
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    if isinstance(v, date):
        return v.isoformat()
    return v


def export(ctx: TenantContext, gages: list[Gage], fmt: str) -> tuple[bytes, str, str]:
    stamp = ctx.today().isoformat()
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Inventory"
        ws.append([h for h, _ in EXPORT_COLUMNS])
        for r in _export_rows(ctx, gages):
            ws.append([float(v) if isinstance(v, Decimal) else v for v in r])
        ws.freeze_panes = "A2"
        buf = io.BytesIO()
        wb.save(buf)
        return (buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"gage-inventory-{stamp}.xlsx")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for h, _ in EXPORT_COLUMNS])
    for r in _export_rows(ctx, gages):
        w.writerow([_fmt(v) if v is not None else "" for v in r])
    return ("﻿" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8", f"gage-inventory-{stamp}.csv"
