import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response

from app.modules.compliance import service
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P

router = APIRouter(tags=["compliance"])


@router.get("/compliance/matrix")
def matrix(ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return service.matrix(ctx)


@router.get("/compliance/processes/{code}")
def process(code: str, ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return service.process_evidence(ctx, code.upper()) | {"disclaimer": service.DISCLAIMER}


@router.get("/compliance/clauses")
def clauses(_: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return {"disclaimer": service.DISCLAIMER, "clauses": service.CLAUSES}


@router.get("/compliance/clauses/{standard}/{number}")
def clause(standard: str, number: str, ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return service.clause(ctx, standard, number)


@router.get("/compliance/gages/{gage_id}/dossier")
def dossier(gage_id: uuid.UUID, ctx: TenantContext = Depends(require(P.COMPLIANCE_READ, P.GAGES_READ))):
    return service.dossier(ctx, gage_id)


@router.get("/compliance/certificates")
def certificates(q: str | None = Query(default=None, max_length=100), valid_on: date | None = None,
                 ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return service.certificates(ctx, q, valid_on)


@router.get("/compliance/approvals")
def approvals(since: date | None = None, until: date | None = None,
              ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    until = until or ctx.today()
    return service.approvals(ctx, since or until - timedelta(days=90), until)


@router.get("/compliance/pending")
def pending(ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    return service.pending(ctx)


@router.get("/compliance/export.xlsx")
def export(gage_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require(P.COMPLIANCE_READ))):
    data = service.export_xlsx(ctx, gage_id)
    ctx.audit(action="compliance.exported", entity_type="compliance_export", entity_id=gage_id,
              changes={"gage_id": str(gage_id) if gage_id else None})
    ctx.db.commit()
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="compliance-evidence.xlsx"'})
