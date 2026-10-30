import secrets
import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.identity.deps import TenantContext, require
from app.modules.organizations.router import get_plant
from app.modules.reports import render
from app.modules.reports.definitions import REPORTS, Params

router = APIRouter(tags=["reports"])
MEDIA = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "csv": "text/csv; charset=utf-8"}


@router.get("/reports")
def catalogue(lang: Literal["es", "en"] | None = None, ctx: TenantContext = Depends(require())):
    lang = lang or ctx.user.preferred_language or "es"
    return [{"key": r.key, "group": r.group, "title": getattr(r, lang), "needs_gage": r.needs_gage,
             "uses_period": r.uses_period, "columns": [{"key": c.key, "label": getattr(c, lang)} for c in r.columns]}
            for r in REPORTS.values() if ctx.has(r.permission)]


@router.get("/reports/{key}")
def generate(key: str, format: Literal["json", "pdf", "xlsx", "csv"] = "json",
             lang: Literal["es", "en"] | None = None, plant_id: uuid.UUID | None = None,
             date_from: date | None = None, date_to: date | None = None,
             status: str | None = Query(default=None, max_length=30), gage_id: uuid.UUID | None = None,
             ctx: TenantContext = Depends(require())):
    report = REPORTS.get(key)
    if report is None:
        raise NotFoundError("Unknown report")
    ctx.ensure(report.permission)
    lang = lang or ctx.user.preferred_language or "es"
    plant = get_plant(ctx, plant_id) if plant_id else None
    if report.needs_gage and gage_id is None:
        raise BusinessRuleError("Select a gage for this report", code="gage_required")
    params = Params(plant_id=plant_id, date_from=date_from, date_to=date_to, status=status, gage_id=gage_id)
    rows = report.query(ctx, params)
    now = datetime.now(ZoneInfo(ctx.organization.timezone))
    code = f"RPT-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2).upper()}"
    filters = ", ".join(f"{k}={v}" for k, v in (("from", date_from), ("to", date_to), ("status", status),
                                                 ("gage", gage_id)) if v)
    if format == "json":
        return {"code": code, "title": getattr(report, lang), "generated_at": now.isoformat(timespec="seconds"),
                "columns": [{"key": c.key, "label": getattr(c, lang)} for c in report.columns], "rows": rows,
                "count": len(rows)}
    meta = render.Meta(code=code, title=getattr(report, lang), organization=ctx.organization.name,
                       plant=f"{plant.code} · {plant.name}" if plant else None,
                       generated_at=now.strftime("%Y-%m-%d %H:%M %Z"), generated_by=ctx.user.full_name,
                       filters=filters, lang=lang)
    data = {"pdf": render.pdf, "xlsx": render.xlsx, "csv": render.to_csv}[format](meta, report.columns, rows)
    ctx.audit(action="report.generated", entity_type="report", entity_id=code,
              changes={"report": key, "format": format, "rows": len(rows), "plant_id": str(plant_id) if plant_id else None,
                       "filters": filters})
    ctx.db.commit()
    return Response(data, media_type=MEDIA[format],
                    headers={"Content-Disposition": f'attachment; filename="{key}-{now:%Y%m%d}.{format}"',
                             "Cache-Control": "private, no-store"})
