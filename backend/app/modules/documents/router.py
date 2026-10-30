import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import BusinessRuleError
from app.core.storage import get_storage
from app.modules.documents import service
from app.modules.documents.models import Attachment
from app.modules.identity.deps import TenantContext, get_tenant_context
from app.modules.identity.models import User

router = APIRouter(prefix="/attachments", tags=["documents"])


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    category: str
    title: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    is_locked: bool
    uploaded_by: uuid.UUID
    uploaded_by_name: str | None = None
    uploaded_at: datetime
    removed_at: datetime | None
    removal_reason: str | None


class RemoveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def to_out(ctx: TenantContext, items: list[Attachment]) -> list[AttachmentOut]:
    ids = {a.uploaded_by for a in items}
    names = {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))} if ids else {}
    return [AttachmentOut.model_validate(a).model_copy(update={"uploaded_by_name": names.get(a.uploaded_by)})
            for a in items]


@router.get("", response_model=list[AttachmentOut])
def list_attachments(entity_type: str, entity_id: uuid.UUID, include_removed: bool = False,
                     ctx: TenantContext = Depends(get_tenant_context)):
    return to_out(ctx, service.list_for(ctx, entity_type, entity_id, include_removed))


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    entity_type: str = Form(...),
    entity_id: uuid.UUID = Form(...),
    category: str = Form("DOCUMENT"),
    title: str | None = Form(None, max_length=200),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Generic upload. Certificates of calibrations/standards use their own endpoints."""
    service.check_access(ctx, entity_type, entity_id, write=True)
    if category == "CERTIFICATE":
        raise BusinessRuleError("Certificates are registered through the certificate endpoints",
                                code="use_certificate_endpoint")
    data = await file.read()
    att = service.store(ctx, entity_type=entity_type, entity_id=entity_id, category=category,
                        filename=file.filename or "file", data=data, title=title)
    ctx.db.commit()
    return to_out(ctx, [att])[0]


@router.get("/{attachment_id}/download")
def download_attachment(attachment_id: uuid.UUID, ctx: TenantContext = Depends(get_tenant_context)):
    att = service.get_attachment(ctx, attachment_id)
    data = get_storage().get(att.storage_key)
    # Access to controlled documents is part of the audit trail.
    ctx.audit(action="document.downloaded", entity_type=att.entity_type, entity_id=att.entity_id,
              changes={"document_id": str(att.id), "filename": att.original_filename})
    ctx.db.commit()
    disposition = "inline" if att.content_type in ("application/pdf", "image/png", "image/jpeg", "image/webp") else "attachment"
    return Response(
        content=data,
        media_type=att.content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(att.original_filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{attachment_id}/remove", response_model=AttachmentOut)
def remove_attachment(attachment_id: uuid.UUID, body: RemoveIn, ctx: TenantContext = Depends(get_tenant_context)):
    att = service.remove(ctx, attachment_id, body.reason.strip())
    ctx.db.commit()
    return to_out(ctx, [att])[0]
