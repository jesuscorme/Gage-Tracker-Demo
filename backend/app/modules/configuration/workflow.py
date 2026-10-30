"""Configurable workflow engine.

Each record of a workflow entity keeps the version of the workflow it started with
(0 = the built-in default), so editing a workflow never strands records in states the
new version no longer has. Every transition checks, in order: current state, RBAC
permission, approval matrix, personal authorization, segregation of duties, required
comment, business rules and the owning module's domain prerequisites. Transitions that
need several approvals record votes until the quorum of distinct users is reached.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, BusinessRuleError, ConflictError, NotFoundError
from app.modules.competency import service as competency
from app.modules.configuration import registry
from app.modules.configuration import service as config
from app.modules.configuration.models import ConfigItem, ConfigVersion, WorkflowEvent
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import OrganizationMembership, Permission, Role, role_permissions
from app.modules.notifications.models import Notification


def entity(entity_type: str) -> registry.WorkflowEntity:
    ent = registry.WORKFLOW_ENTITIES.get(entity_type)
    if ent is None:
        raise NotFoundError("Unknown workflow entity")
    return ent


def definition(ctx: TenantContext, entity_type: str, version: int) -> dict:
    ent = entity(entity_type)
    if version == 0:
        return ent.default_definition
    return config.definition_version(ctx, "WORKFLOW", entity_type, version) or ent.default_definition


def version_for_new(ctx: TenantContext, entity_type: str) -> int:
    found = config.active_definition(ctx, "WORKFLOW", entity_type)
    return found[0] if found else 0


def initial_state(ctx: TenantContext, entity_type: str, version: int) -> str:
    return definition(ctx, entity_type, version)["initial"]


def _state(defn: dict, code: str) -> dict:
    return next((s for s in defn["states"] if s["code"] == code), {"code": code, "label": code, "capabilities": []})


def capabilities(ctx: TenantContext, entity_type: str, record) -> set[str]:
    ent = entity(entity_type)
    defn = definition(ctx, entity_type, ent.get_version(record))
    return set(_state(defn, ent.get_state(record))["capabilities"])


def ensure_capability(ctx: TenantContext, entity_type: str, record, capability: str) -> None:
    if capability not in capabilities(ctx, entity_type, record):
        ent = entity(entity_type)
        raise ConflictError(f"This operation is not allowed in state {ent.get_state(record)}",
                            code="state_not_allowed", details={"capability": capability,
                                                               "state": ent.get_state(record)})


def record_created(ctx: TenantContext, entity_type: str, record, record_id: uuid.UUID) -> None:
    ent = entity(entity_type)
    ctx.db.add(WorkflowEvent(organization_id=ctx.organization_id, entity_type=entity_type, entity_id=record_id,
                             event_type="CREATED", workflow_version=ent.get_version(record),
                             to_state=ent.get_state(record), actor_id=ctx.user_id))


def _last_state_change(ctx: TenantContext, entity_type: str, record_id: uuid.UUID) -> datetime | None:
    return ctx.db.scalar(select(func.max(WorkflowEvent.occurred_at)).where(
        WorkflowEvent.entity_type == entity_type, WorkflowEvent.entity_id == record_id,
        WorkflowEvent.event_type.in_(("CREATED", "TRANSITION"))))


def _votes(ctx: TenantContext, entity_type: str, record_id: uuid.UUID, transition: str) -> list[uuid.UUID]:
    since = _last_state_change(ctx, entity_type, record_id)
    stmt = select(WorkflowEvent.actor_id).where(
        WorkflowEvent.entity_type == entity_type, WorkflowEvent.entity_id == record_id,
        WorkflowEvent.event_type == "VOTE", WorkflowEvent.transition == transition)
    if since is not None:
        stmt = stmt.where(WorkflowEvent.occurred_at >= since)
    return list(ctx.db.scalars(stmt))


def _previous_actor(ctx: TenantContext, entity_type: str, record_id: uuid.UUID) -> uuid.UUID | None:
    return ctx.db.scalar(select(WorkflowEvent.actor_id).where(
        WorkflowEvent.entity_type == entity_type, WorkflowEvent.entity_id == record_id,
        WorkflowEvent.event_type == "TRANSITION").order_by(WorkflowEvent.occurred_at.desc()).limit(1))


def _check(ctx: TenantContext, ent: registry.WorkflowEntity, record, record_id, t: dict, comment: str | None) -> None:
    """Raise the first reason that prevents the current user from taking transition ``t``."""
    state = ent.get_state(record)
    if state not in t["from_states"]:
        raise ConflictError(f"Transition {t['code']} is not available in state {state}", code="invalid_transition")
    ctx.ensure(t["permission"])
    plant = ent.plant_of(record) if ent.plant_of else None
    if t.get("action", "ADVANCE") != "ADVANCE":
        config.ensure_approval(ctx, ent.entity_type, t["action"], plant_id=plant)
    if t.get("authorization"):
        competency.ensure_authorized(ctx, ctx.user_id, t["authorization"], plant_id=plant)
    parties = ent.parties(record) if ent.parties else {}
    for party in t.get("segregate_from") or []:
        uid = _previous_actor(ctx, ent.entity_type, record_id) if party == "previous_actor" else parties.get(party)
        if uid is not None and uid == ctx.user_id:
            raise BusinessRuleError(f"Segregation of duties: the {party.replace('_', ' ')} cannot perform "
                                    f"'{t['label']}'", code="segregation_of_duties", details={"party": party})
    if t.get("require_comment") and not (comment or "").strip():
        raise BusinessRuleError("A comment is required for this transition", code="comment_required")
    if ctx.user_id in _votes(ctx, ent.entity_type, record_id, t["code"]):
        raise ConflictError("You already approved this step; another approver is required", code="already_voted")


def available(ctx: TenantContext, entity_type: str, record, record_id: uuid.UUID) -> list[dict]:
    ent = entity(entity_type)
    defn = definition(ctx, entity_type, ent.get_version(record))
    out = []
    for t in defn["transitions"]:
        if ent.get_state(record) not in t["from_states"]:
            continue
        reason = None
        try:
            _check(ctx, ent, record, record_id, t, comment="-")
        except AppError as exc:
            reason = exc.message
        out.append({"code": t["code"], "label": t["label"], "to": t["to"], "action": t.get("action", "ADVANCE"),
                    "require_comment": t.get("require_comment", False),
                    "approvals_required": t.get("approvals_required", 1),
                    "votes": len(_votes(ctx, entity_type, record_id, t["code"])),
                    "allowed": reason is None, "reason": reason})
    return out


def transition(ctx: TenantContext, entity_type: str, record, record_id: uuid.UUID, code: str,
               comment: str | None) -> dict:
    """Apply a transition in the current transaction (the caller commits)."""
    ent = entity(entity_type)
    version = ent.get_version(record)
    defn = definition(ctx, entity_type, version)
    t = next((x for x in defn["transitions"] if x["code"] == code), None)
    if t is None:
        raise BusinessRuleError(f"Unknown transition {code}", code="invalid_transition")
    _check(ctx, ent, record, record_id, t, comment)
    facts = ent.compute_facts(ctx, record) if ent.compute_facts else {}
    blocks, warnings = config.evaluate_rules(ctx, entity_type, code, facts)
    if blocks:
        raise BusinessRuleError("Business rules block this transition", code="business_rule_blocked",
                                details=blocks)
    if ent.before_enter:
        ent.before_enter(ctx, record, t["to"])
    from_state = ent.get_state(record)
    required = t.get("approvals_required", 1)
    if required > 1:
        votes = _votes(ctx, entity_type, record_id, code)
        ctx.db.add(WorkflowEvent(organization_id=ctx.organization_id, entity_type=entity_type, entity_id=record_id,
                                 event_type="VOTE", workflow_version=version, transition=code,
                                 action=t.get("action"), from_state=from_state, comment=comment,
                                 actor_id=ctx.user_id))
        ctx.audit(action=f"{entity_type}.approval_vote", entity_type=entity_type, entity_id=record_id,
                  changes={"transition": code, "votes": [len(votes), len(votes) + 1], "required": required},
                  reason=comment)
        if len(votes) + 1 < required:
            ctx.db.flush()
            return {"moved": False, "state": from_state, "votes": len(votes) + 1, "required": required,
                    "warnings": warnings}
    ent.set_state(ctx, record, t["to"])
    ctx.db.add(WorkflowEvent(organization_id=ctx.organization_id, entity_type=entity_type, entity_id=record_id,
                             event_type="TRANSITION", workflow_version=version, transition=code,
                             action=t.get("action"), from_state=from_state, to_state=t["to"], comment=comment,
                             data={"warnings": warnings} if warnings else None, actor_id=ctx.user_id))
    ctx.audit(action=f"{entity_type}.transition", entity_type=entity_type, entity_id=record_id,
              changes={"status": [from_state, t["to"]], "transition": code, "workflow_version": version},
              reason=comment)
    ctx.db.flush()
    if ent.after_enter:
        ent.after_enter(ctx, record, from_state, t["to"])
    return {"moved": True, "state": t["to"], "votes": required, "required": required, "warnings": warnings}


def system_transition(ctx: TenantContext, entity_type: str, record, record_id: uuid.UUID, to_state: str,
                      comment: str) -> None:
    """State change performed automatically by the system (e.g. restriction on detection).

    Recorded like any transition (actor = user whose operation triggered it), but without
    the interactive checks, which belong to that triggering operation.
    """
    ent = entity(entity_type)
    from_state = ent.get_state(record)
    ent.set_state(ctx, record, to_state)
    ctx.db.add(WorkflowEvent(organization_id=ctx.organization_id, entity_type=entity_type, entity_id=record_id,
                             event_type="TRANSITION", workflow_version=ent.get_version(record), transition="SYSTEM",
                             action="ADVANCE", from_state=from_state, to_state=to_state, comment=comment,
                             actor_id=ctx.user_id))
    ctx.audit(action=f"{entity_type}.transition", entity_type=entity_type, entity_id=record_id,
              changes={"status": [from_state, to_state], "transition": "SYSTEM"}, reason=comment)


def history(ctx: TenantContext, entity_type: str, record_id: uuid.UUID) -> list[WorkflowEvent]:
    return list(ctx.db.scalars(select(WorkflowEvent).where(
        WorkflowEvent.organization_id == ctx.organization_id, WorkflowEvent.entity_type == entity_type,
        WorkflowEvent.entity_id == record_id).order_by(WorkflowEvent.occurred_at, WorkflowEvent.id)))


# ---------------------------------------------------------------- escalation

def _definition_for(db: Session, org_id: uuid.UUID, entity_type: str, version: int) -> dict:
    if version == 0:
        return entity(entity_type).default_definition
    d = db.scalar(select(ConfigVersion.definition).join(ConfigItem, ConfigItem.id == ConfigVersion.item_id).where(
        ConfigItem.organization_id == org_id, ConfigItem.kind == "WORKFLOW", ConfigItem.key == entity_type,
        ConfigVersion.version == version))
    return d or entity(entity_type).default_definition


def escalate_due(db: Session, now: datetime | None = None, organization_id: uuid.UUID | None = None) -> int:
    """Notify when a record stays in a state longer than its escalation threshold.

    One escalation event per (record, state entry, rule); safe to run repeatedly.
    """
    now = now or datetime.now(UTC)
    latest_q = (select(WorkflowEvent.entity_type, WorkflowEvent.entity_id,
                       func.max(WorkflowEvent.occurred_at).label("at"))
                .where(WorkflowEvent.event_type.in_(("CREATED", "TRANSITION"))))
    if organization_id is not None:
        latest_q = latest_q.where(WorkflowEvent.organization_id == organization_id)
    latest = latest_q.group_by(WorkflowEvent.entity_type, WorkflowEvent.entity_id).subquery()
    rows = db.execute(select(WorkflowEvent).join(latest, and_(
        WorkflowEvent.entity_type == latest.c.entity_type, WorkflowEvent.entity_id == latest.c.entity_id,
        WorkflowEvent.occurred_at == latest.c.at)).where(WorkflowEvent.event_type.in_(("CREATED", "TRANSITION"))))
    sent = 0
    for (ev,) in rows:
        if ev.entity_type not in registry.WORKFLOW_ENTITIES:
            continue
        defn = _definition_for(db, ev.organization_id, ev.entity_type, ev.workflow_version)
        for i, rule in enumerate(defn.get("escalations") or []):
            if rule["state"] != ev.to_state or now - ev.occurred_at < timedelta(hours=rule["after_hours"]):
                continue
            done = db.scalar(select(WorkflowEvent.id).where(
                WorkflowEvent.entity_type == ev.entity_type, WorkflowEvent.entity_id == ev.entity_id,
                WorkflowEvent.event_type == "ESCALATION", WorkflowEvent.occurred_at >= ev.occurred_at,
                WorkflowEvent.transition == f"ESC{i}"))
            if done:
                continue
            users = db.scalars(
                select(OrganizationMembership.user_id).join(Role, Role.id == OrganizationMembership.role_id)
                .join(role_permissions, role_permissions.c.role_id == Role.id)
                .join(Permission, Permission.code == role_permissions.c.permission_code)
                .where(OrganizationMembership.organization_id == ev.organization_id,
                       OrganizationMembership.is_active.is_(True), Permission.code == rule["notify_permission"]))
            for uid in set(users):
                db.add(Notification(organization_id=ev.organization_id, user_id=uid, kind="workflow.escalation",
                                    title=f"{ev.entity_type} waiting in {ev.to_state} for more than "
                                          f"{rule['after_hours']} h",
                                    link=f"{entity(ev.entity_type).link_prefix}{ev.entity_id}"))
            db.add(WorkflowEvent(organization_id=ev.organization_id, entity_type=ev.entity_type,
                                 entity_id=ev.entity_id, event_type="ESCALATION",
                                 workflow_version=ev.workflow_version, transition=f"ESC{i}",
                                 from_state=ev.to_state, data={"after_hours": rule["after_hours"]}))
            sent += 1
    db.commit()
    return sent
