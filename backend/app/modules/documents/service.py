"""Documents attached to business records.

Each module registers its entity types with the permissions needed to read and to
attach files, plus a loader that enforces tenant and plant scope. Access to a file is
always decided by access to the record it belongs to.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.storage import IMAGE_TYPES, get_storage, validate_upload
from app.modules.documents.models import CATEGORIES, Attachment
from app.modules.identity.deps import TenantContext


@dataclass(frozen=True)
class EntityKind:
    read_permission: str
    write_permission: str
    # Loads the record within the tenant/plant scope or raises NotFoundError.
    loader: Callable[[TenantContext, uuid.UUID], object]


_REGISTRY: dict[str, EntityKind] = {}


def register(entity_type: str, read_permission: str, write_permission: str,
             loader: Callable[[TenantContext, uuid.UUID], object]) -> None:
    _REGISTRY[entity_type] = EntityKind(read_permission, write_permission, loader)


def check_access(ctx: TenantContext, entity_type: str, entity_id: uuid.UUID, *, write: bool) -> None:
    kind = _REGISTRY.get(entity_type)
    if kind is None:
        raise BusinessRuleError("Unsupported entity type", code="invalid_entity_type",
                                details={"allowed": sorted(_REGISTRY)})
    ctx.ensure(kind.read_permission)
    kind.loader(ctx, entity_id)
    if write:
        ctx.ensure(kind.write_permission)


def store(
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    category: str,
    filename: str,
    data: bytes,
    title: str | None = None,
    locked: bool = False,
    pdf_only: bool = False,
    images_only: bool = False,
) -> Attachment:
    """Validate and store a file (caller has already checked access to the entity)."""
    if category not in CATEGORIES:
        raise BusinessRuleError("Invalid document category", code="invalid_category")
    ctype = validate_upload(filename, data)
    if pdf_only and ctype != "application/pdf":
        raise BusinessRuleError("A PDF file is required", code="pdf_required")
    if (images_only or category == "PHOTO") and ctype not in IMAGE_TYPES:
        raise BusinessRuleError("Photos must be PNG, JPEG or WEBP", code="image_required")
    key, digest = get_storage().put(ctx.organization_id, data)
    att = Attachment(
        organization_id=ctx.organization_id, entity_type=entity_type, entity_id=entity_id,
        category=category, title=(title or "").strip() or None, original_filename=filename[-255:],
        content_type=ctype, size_bytes=len(data), sha256=digest, storage_key=key,
        is_locked=locked, uploaded_by=ctx.user_id,
    )
    ctx.db.add(att)
    ctx.db.flush()
    ctx.audit(action="document.uploaded", entity_type=entity_type, entity_id=entity_id,
              changes={"document_id": str(att.id), "category": category, "filename": att.original_filename,
                       "sha256": digest, "size": len(data)})
    return att


def get_attachment(ctx: TenantContext, attachment_id: uuid.UUID) -> Attachment:
    att = ctx.db.scalar(select(Attachment).where(
        Attachment.id == attachment_id, Attachment.organization_id == ctx.organization_id))
    if att is None:
        raise NotFoundError("Document not found")
    try:
        check_access(ctx, att.entity_type, att.entity_id, write=False)
    except NotFoundError:
        raise NotFoundError("Document not found")
    return att


def list_for(ctx: TenantContext, entity_type: str, entity_id: uuid.UUID, include_removed: bool) -> list[Attachment]:
    check_access(ctx, entity_type, entity_id, write=False)
    stmt = select(Attachment).where(
        Attachment.organization_id == ctx.organization_id,
        Attachment.entity_type == entity_type, Attachment.entity_id == entity_id,
    )
    if not include_removed:
        stmt = stmt.where(Attachment.removed_at.is_(None))
    return list(ctx.db.scalars(stmt.order_by(Attachment.uploaded_at.desc())))


def lock(att: Attachment) -> None:
    att.is_locked = True


def remove(ctx: TenantContext, attachment_id: uuid.UUID, reason: str) -> Attachment:
    att = get_attachment(ctx, attachment_id)
    check_access(ctx, att.entity_type, att.entity_id, write=True)
    if att.is_locked:
        raise ConflictError("This document supports an approved record and cannot be withdrawn",
                            code="document_locked")
    if att.removed_at:
        return att
    att.removed_at = datetime.now(UTC)
    att.removed_by = ctx.user_id
    att.removal_reason = reason
    ctx.audit(action="document.removed", entity_type=att.entity_type, entity_id=att.entity_id,
              changes={"document_id": str(att.id), "filename": att.original_filename}, reason=reason)
    return att
