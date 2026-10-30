"""Import framework (CSV / Excel).

Flow: upload -> column mapping -> validation through the owning module's domain service
inside a savepoint that is always rolled back (nothing is persisted) -> preview and
per-row errors -> commit, which re-validates and applies every row in one transaction
(all or nothing). The original file is kept, so a job can be reprocessed with another
mapping. Each importer delegates to domain services; no business rule is duplicated.
"""

import csv
import io
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from openpyxl import Workbook, load_workbook
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import AppError, BusinessRuleError, ConflictError, NotFoundError
from app.core.storage import get_storage
from app.modules.documents import service as documents
from app.modules.documents.models import Attachment
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.integrations.models import ImportJob

MAX_ROWS = 5000
PREVIEW_ROWS = 20


@dataclass(frozen=True)
class ImportField:
    name: str
    required: bool = False
    description: str = ""
    aliases: tuple[str, ...] = ()


@dataclass
class Importer:
    code: str
    label: str
    permission: str
    fields: list[ImportField]
    # (ctx, rows, target_id, job_id) -> (rows applied, row errors); may raise AppError.
    run: Callable
    target_label: str | None = None
    key_fields: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_target(self) -> bool:
        return self.target_label is not None


IMPORTERS: dict[str, Importer] = {}


def register(importer: Importer) -> None:
    IMPORTERS[importer.code] = importer


def importer(code: str) -> Importer:
    if code not in IMPORTERS:
        raise NotFoundError("Unknown importer")
    return IMPORTERS[code]


# ---------------------------------------------------------------- file reading and mapping

def _cell(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def read_table(filename: str, data: bytes) -> tuple[list[str], list[dict[str, str | None]]]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise BusinessRuleError("The Excel file could not be read", code="invalid_file")
        raw = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    elif name.endswith(".csv"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise BusinessRuleError("CSV must be UTF-8 encoded", code="invalid_encoding")
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t") if text.strip() else csv.excel
        raw = list(csv.reader(io.StringIO(text), dialect))
    else:
        raise BusinessRuleError("Use a .csv or .xlsx file", code="invalid_file_type")
    if not raw:
        raise BusinessRuleError("The file is empty", code="empty_file")
    headers = [(_cell(h) or f"column_{i + 1}") for i, h in enumerate(raw[0])]
    if len(set(h.lower() for h in headers)) != len(headers):
        raise BusinessRuleError("Column names must be unique", code="duplicate_columns")
    rows = []
    for r in raw[1:]:
        cells = [_cell(v) for v in r]
        if not any(cells):
            continue
        rows.append({h: (cells[i] if i < len(cells) else None) for i, h in enumerate(headers)})
    if len(rows) > MAX_ROWS:
        raise BusinessRuleError(f"At most {MAX_ROWS} rows per import", code="too_many_rows")
    return headers, rows


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def default_mapping(imp: Importer, headers: list[str]) -> dict[str, str]:
    by_norm = {_norm(h): h for h in headers}
    out = {}
    for f in imp.fields:
        for candidate in (f.name, *f.aliases):
            if _norm(candidate) in by_norm:
                out[f.name] = by_norm[_norm(candidate)]
                break
    return out


def apply_mapping(imp: Importer, headers: list[str], rows: list[dict], mapping: dict[str, str]) -> list[dict]:
    known = {f.name for f in imp.fields}
    problems = [f"unknown target field '{k}'" for k in mapping if k not in known]
    problems += [f"column '{v}' is not in the file" for v in mapping.values() if v not in headers]
    problems += [f"required field '{f.name}' is not mapped" for f in imp.fields if f.required and f.name not in mapping]
    if len(set(mapping.values())) != len(mapping):
        problems.append("a file column is mapped to more than one field")
    if problems:
        raise BusinessRuleError("The column mapping is not valid", code="invalid_mapping", details=problems)
    return [{target: row.get(source) for target, source in mapping.items()} for row in rows]


def _duplicates(imp: Importer, rows: list[dict]) -> list[dict]:
    if not imp.key_fields:
        return []
    seen: dict[tuple, int] = {}
    errors = []
    for i, r in enumerate(rows, start=2):
        key = tuple((r.get(k) or "").strip().upper() for k in imp.key_fields)
        if not all(key):
            continue
        if key in seen:
            errors.append({"row": i, "errors": [f"duplicate of row {seen[key]} ({', '.join(imp.key_fields)})"]})
        else:
            seen[key] = i
    return errors


# ---------------------------------------------------------------- jobs

def _check_target(ctx: TenantContext, imp: Importer, target_id: uuid.UUID | None) -> None:
    if imp.needs_target and target_id is None:
        raise BusinessRuleError(f"{imp.target_label} is required for this import", code="target_required")


def _evaluate(ctx: TenantContext, imp: Importer, mapped: list[dict], target_id, job_id) -> tuple[int, list[dict]]:
    """Run the importer inside a savepoint that is always rolled back (validation only)."""
    errors = _duplicates(imp, mapped)
    if errors:
        return 0, errors
    sp = ctx.db.begin_nested()
    try:
        applied, errors = imp.run(ctx, mapped, target_id, job_id)
    except AppError as exc:
        applied, errors = 0, [{"row": None, "errors": [exc.message], "details": exc.details}]
    finally:
        sp.rollback()
    return applied, errors


def _finish_validation(ctx: TenantContext, job: ImportJob, imp: Importer, headers, rows, mapping) -> ImportJob:
    try:
        mapped = apply_mapping(imp, headers, rows, mapping)
        valid, errors = _evaluate(ctx, imp, mapped, job.target_id, job.id)
    except AppError as exc:
        mapped, valid, errors = [], 0, [{"row": None, "errors": [exc.message], "details": exc.details}]
    job.total_rows, job.valid_rows = len(rows), (len(rows) if not errors else valid)
    job.errors, job.error_count = errors[:500], len(errors)
    job.preview = mapped[:PREVIEW_ROWS]
    job.status = "VALIDATED" if not errors and rows else "INVALID"
    if not rows:
        job.errors, job.error_count = [{"row": None, "errors": ["the file has no data rows"]}], 1
    return job


def create_job(ctx: TenantContext, code: str, filename: str, data: bytes, mapping: dict[str, str] | None,
               target_id: uuid.UUID | None) -> ImportJob:
    imp = importer(code)
    ctx.ensure(imp.permission)
    _check_target(ctx, imp, target_id)
    headers, rows = read_table(filename, data)
    job_id = uuid.uuid4()
    att = documents.store(ctx, entity_type="import_job", entity_id=job_id, category="DOCUMENT", filename=filename,
                          data=data, title=f"Import {imp.label}", locked=True)
    mapping = mapping or default_mapping(imp, headers)
    job = ImportJob(id=job_id, organization_id=ctx.organization_id, importer=code, target_id=target_id,
                    filename=filename[-255:], attachment_id=att.id, mapping=mapping, status="INVALID", total_rows=0,
                    valid_rows=0, error_count=0, errors=[], preview=[], created_by=ctx.user_id)
    _finish_validation(ctx, job, imp, headers, rows, mapping)
    ctx.db.add(job)
    ctx.audit(action="import.validated", entity_type="import_job", entity_id=job.id,
              changes={"importer": code, "filename": job.filename, "rows": job.total_rows, "status": job.status,
                       "errors": job.error_count})
    ctx.db.commit()
    return job


def get_job(ctx: TenantContext, job_id: uuid.UUID, *, for_update: bool = False) -> ImportJob:
    stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.organization_id == ctx.organization_id)
    job = ctx.db.scalar(stmt.with_for_update() if for_update else stmt)
    if job is None:
        raise NotFoundError("Import job not found")
    return job


def list_jobs(ctx: TenantContext, code: str | None, target_id: uuid.UUID | None) -> list[ImportJob]:
    stmt = select(ImportJob).where(ImportJob.organization_id == ctx.organization_id)
    if code:
        stmt = stmt.where(ImportJob.importer == code)
    if target_id:
        stmt = stmt.where(ImportJob.target_id == target_id)
    return list(ctx.db.scalars(stmt.order_by(ImportJob.created_at.desc()).limit(200)))


def _file(ctx: TenantContext, job: ImportJob) -> bytes:
    att = ctx.db.get(Attachment, job.attachment_id)
    return get_storage().get(att.storage_key)


def commit_job(ctx: TenantContext, job_id: uuid.UUID) -> ImportJob:
    job = get_job(ctx, job_id, for_update=True)
    imp = importer(job.importer)
    ctx.ensure(imp.permission)
    if job.status != "VALIDATED":
        raise ConflictError(f"Only validated jobs can be committed (status {job.status})", code="invalid_status")
    headers, rows = read_table(job.filename, _file(ctx, job))
    mapped = apply_mapping(imp, headers, rows, job.mapping)
    errors = _duplicates(imp, mapped)
    applied = 0
    if not errors:
        sp = ctx.db.begin_nested()
        try:
            applied, errors = imp.run(ctx, mapped, job.target_id, job.id)
        except AppError as exc:
            errors = [{"row": None, "errors": [exc.message], "details": exc.details}]
        if errors:
            sp.rollback()
        else:
            sp.commit()
    if errors:
        # Data changed since validation: nothing is applied, the job records why.
        job.status, job.errors, job.error_count = "INVALID", errors[:500], len(errors)
        ctx.audit(action="import.rejected", entity_type="import_job", entity_id=job.id,
                  changes={"errors": len(errors)})
        ctx.db.commit()
        return job
    job.status, job.committed_by, job.committed_at = "COMMITTED", ctx.user_id, datetime.now(UTC)
    job.summary = {"applied": applied, "rows": len(rows)}
    ctx.audit(action="import.committed", entity_type="import_job", entity_id=job.id,
              changes={"importer": job.importer, "rows": len(rows), "applied": applied, "filename": job.filename})
    ctx.db.commit()
    return job


def reprocess(ctx: TenantContext, job_id: uuid.UUID, mapping: dict[str, str]) -> ImportJob:
    """Validate the stored file again with another mapping (new job; the original is kept)."""
    old = get_job(ctx, job_id)
    imp = importer(old.importer)
    ctx.ensure(imp.permission)
    headers, rows = read_table(old.filename, _file(ctx, old))
    job = ImportJob(organization_id=ctx.organization_id, importer=old.importer, target_id=old.target_id,
                    filename=old.filename, attachment_id=old.attachment_id, mapping=mapping, status="INVALID",
                    total_rows=0, valid_rows=0, error_count=0, errors=[], preview=[], reprocess_of_id=old.id,
                    created_by=ctx.user_id)
    ctx.db.add(job)
    ctx.db.flush()
    _finish_validation(ctx, job, imp, headers, rows, mapping)
    ctx.audit(action="import.reprocessed", entity_type="import_job", entity_id=job.id,
              changes={"from": str(old.id), "status": job.status, "errors": job.error_count})
    ctx.db.commit()
    return job


def template(code: str) -> bytes:
    imp = importer(code)
    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append([f.name for f in imp.fields])
    help_ws = wb.create_sheet("fields")
    help_ws.append(["field", "required", "description"])
    for f in imp.fields:
        help_ws.append([f.name, "yes" if f.required else "no", f.description])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- importers

def _run_gages(ctx: TenantContext, rows: list[dict], target_id, job_id) -> tuple[int, list[dict]]:
    from app.modules.gages import io as gage_io
    from app.modules.gages import service as gages
    from app.modules.gages.schemas import GageCreate

    lookups = gage_io._lookups(ctx)
    errors, applied = [], 0
    for i, row in enumerate(rows, start=2):
        payload, row_errors = gage_io._to_payload({k: v for k, v in row.items()}, lookups)
        if not row_errors:
            try:
                with ctx.db.begin_nested():
                    gages.build_gage(ctx, GageCreate(**payload))
                applied += 1
            except ValidationError as exc:
                row_errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            except AppError as exc:
                row_errors = [exc.message]
        if row_errors:
            errors.append({"row": i, "key": row.get("gage_code"), "errors": row_errors})
    return applied, errors


def _run_msa(ctx: TenantContext, rows: list[dict], target_id, job_id) -> tuple[int, list[dict]]:
    from app.modules.msa import service as msa

    study = msa.get_study(ctx, target_id, for_update=True)
    try:
        created = msa.build_observations(ctx, study, rows, source="IMPORT", import_job_id=job_id)
    except BusinessRuleError as exc:
        if exc.code == "invalid_observations":
            return 0, [{"row": d.get("row", 0) + 1 if d.get("row") else None, "field": d.get("field"),
                        "errors": [d["message"]]} for d in exc.details]
        raise
    return len(created), []


def _register_builtin() -> None:
    from app.modules.gages import io as gage_io

    register(Importer(
        code="gages", label="Gage inventory", permission=P.GAGES_IMPORT, run=_run_gages, key_fields=("gage_code",),
        fields=[ImportField(c, c in gage_io.REQUIRED, aliases=a) for c, a in (
            ("gage_code", ("gage id", "id", "codigo")), ("description", ("descripcion",)),
            ("gage_type_code", ("type", "tipo")), ("plant_code", ("plant", "planta")),
            ("department_code", ("department", "departamento")), ("location", ("ubicacion",)),
            ("responsible_email", ("responsible", "responsable")), ("manufacturer", ("fabricante",)),
            ("model", ("modelo",)), ("serial_number", ("serial", "serie")), ("range_min", ()), ("range_max", ()),
            ("unit", ("unidad",)), ("resolution", ("resolucion",)), ("accuracy", ("exactitud",)),
            ("criticality", ("criticidad",)), ("calibration_frequency_days", ("frequency", "frecuencia")),
            ("last_calibration_date", ()), ("acquisition_date", ()), ("in_service_date", ()), ("notes", ("notas",)))]))
    register(Importer(
        code="msa_observations", label="MSA study data", permission=P.MSA_MANAGE, run=_run_msa,
        target_label="MSA study",
        fields=[ImportField("operator", aliases=("appraiser", "operador", "evaluador")),
                ImportField("part", aliases=("pieza", "part_id")),
                ImportField("trial", aliases=("replica", "repeticion", "repetition")),
                ImportField("subgroup", aliases=("subgrupo",)),
                ImportField("value", aliases=("valor", "measurement", "medicion")),
                ImportField("category", aliases=("categoria", "classification", "clasificacion")),
                ImportField("reference", aliases=("referencia", "reference_value")),
                ImportField("measured_at", aliases=("fecha", "timestamp", "date"))]))


_register_builtin()
