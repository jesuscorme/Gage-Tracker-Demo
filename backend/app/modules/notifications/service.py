"""In-app notifications (delivery by e-mail is not implemented yet)."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select

from app.modules.identity.deps import TenantContext
from app.modules.identity.models import OrganizationMembership, Permission, Role, role_permissions
from app.modules.notifications.models import Notification, NotificationPreference


def notify(ctx: TenantContext, user_ids: Iterable[uuid.UUID | None], kind: str, title: str,
           body: str | None = None, link: str | None = None, *, include_actor: bool = False) -> int:
    """Queue notifications in the current transaction. Respects opt-outs; skips the actor."""
    targets = {u for u in user_ids if u and (include_actor or u != ctx.user_id)}
    if not targets:
        return 0
    disabled = set(ctx.db.scalars(select(NotificationPreference.user_id).where(
        NotificationPreference.organization_id == ctx.organization_id, NotificationPreference.kind == kind,
        NotificationPreference.enabled.is_(False), NotificationPreference.user_id.in_(targets))))
    for uid in targets - disabled:
        ctx.db.add(Notification(organization_id=ctx.organization_id, user_id=uid, kind=kind, title=title,
                                body=body, link=link))
    return len(targets - disabled)


def users_with_permission(ctx: TenantContext, permission: str) -> list[uuid.UUID]:
    return list(ctx.db.scalars(
        select(OrganizationMembership.user_id)
        .join(Role, Role.id == OrganizationMembership.role_id)
        .join(role_permissions, role_permissions.c.role_id == Role.id)
        .join(Permission, Permission.code == role_permissions.c.permission_code)
        .where(OrganizationMembership.organization_id == ctx.organization_id,
               OrganizationMembership.is_active.is_(True), Permission.code == permission)
    ))
