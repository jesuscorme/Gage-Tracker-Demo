"""Versioned configuration, custom field values, approval matrices and business rules."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.modules.competency import service as competency
from app.modules.configuration import definitions as defs
from app.modules.configuration import registry
from app.modules.configuration.models import ConfigItem, ConfigVersion, CustomFieldValue
from app.modules.identity.deps import TenantContext


# ---------------------------------------------------------------- versions

def get_item(ctx: TenantContext, item_id: uuid.UUID) -> ConfigItem:
    item = ctx.db.get(ConfigItem, item_id)
    if item is None or item.organization_id != ctx.organization_id:
        raise NotFoundError("Configuration item not found")
    return item


def get_version(ctx: TenantContext, version_id: uuid.UUID, *, for_update: bool = False) -> ConfigVersion:
    stmt = select(ConfigVersion).where(ConfigVersion.id == version_id,
                                       ConfigVersion.organization_id == ctx.organization_id)
    v = ctx.db.scalar(stmt.with_for_update() if for_update else stmt)
    if v is None:
        raise NotFoundError("Configuration version not found")
    return v


def active_definitions(ctx: TenantContext, kind: str, entity_type: str | None = None) -> list[tuple[ConfigItem, ConfigVersion]]:
    stmt = (select(ConfigItem, ConfigVersion)
            .join(ConfigVersion, (ConfigVersion.item_id == ConfigItem.id)
                  & (ConfigVersion.version == ConfigItem.active_version))
            .where(ConfigItem.organization_id == ctx.organization_id, ConfigItem.kind == kind,
                   ConfigItem.is_retired.is_(False)))
    if entity_type:
        stmt = stmt.where(ConfigItem.entity_type == entity_type)
    return list(ctx.db.execute(stmt.order_by(ConfigItem.key)).tuples())


def active_definition(ctx: TenantContext, kind: str, key: str) -> tuple[int, dict] | None:
    row = ctx.db.execute(
        select(ConfigVersion.version, ConfigVersion.definition)
        .join(ConfigItem, ConfigItem.id == ConfigVersion.item_id)
        .where(ConfigItem.organization_id == ctx.organization_id, ConfigItem.kind == kind, ConfigItem.key == key,
               ConfigItem.is_retired.is_(False), ConfigVersion.version == ConfigItem.active_version)).first()
    return (row[0], row[1]) if row else None


def definition_version(ctx: TenantContext, kind: str, key: str, version: int) -> dict | None:
    return ctx.db.scalar(
        select(ConfigVersion.definition).join(ConfigItem, ConfigItem.id == ConfigVersion.item_id)
        .where(ConfigItem.organization_id == ctx.organization_id, ConfigItem.kind == kind, ConfigItem.key == key,
               ConfigVersion.version == version))


def _custom_keys(ctx: TenantContext, entity_type: str) -> set[str]:
    return {v.definition["key"] for _i, v in active_definitions(ctx, "CUSTOM_FIELD", entity_type)}


def propose(ctx: TenantContext, kind: str, raw: dict, change_summary: str) -> ConfigVersion:
    d = defs.parse(kind, raw)
    keys = _custom_keys(ctx, d.entity_type) if kind in ("CUSTOM_FIELD", "FORM") else None
    if kind == "CUSTOM_FIELD" and keys is not None:
        keys = keys | {d.key}
    defs.validate_semantics(kind, d, custom_field_keys=keys)
    key = defs.item_key(kind, d)
    item = ctx.db.scalar(select(ConfigItem).where(ConfigItem.organization_id == ctx.organization_id,
                                                  ConfigItem.kind == kind, ConfigItem.key == key).with_for_update())
    if item is None:
        item = ConfigItem(organization_id=ctx.organization_id, kind=kind, key=key, entity_type=d.entity_type,
                          created_by=ctx.user_id)
        ctx.db.add(item)
        ctx.db.flush()
    elif ctx.db.scalar(select(ConfigVersion.id).where(ConfigVersion.item_id == item.id,
                                                      ConfigVersion.status == "DRAFT")):
        raise ConflictError("A draft of this configuration is already pending approval", code="draft_pending")
    number = (ctx.db.scalar(select(func.max(ConfigVersion.version)).where(ConfigVersion.item_id == item.id)) or 0) + 1
    v = ConfigVersion(organization_id=ctx.organization_id, item_id=item.id, version=number,
                      definition=d.model_dump(mode="json"), change_summary=change_summary.strip(),
                      status="DRAFT", created_by=ctx.user_id)
    ctx.db.add(v)
    ctx.db.flush()
    ctx.audit(action="config.version_proposed", entity_type="config_item", entity_id=item.id,
              changes={"kind": kind, "key": key, "version": number}, reason=change_summary)
    if kind not in defs.NEEDS_APPROVAL:
        _activate(ctx, item, v, None)
    ctx.db.commit()
    return v


def _activate(ctx: TenantContext, item: ConfigItem, v: ConfigVersion, comment: str | None) -> None:
    previous = item.active_version
    if previous is not None:
        old = ctx.db.scalar(select(ConfigVersion).where(ConfigVersion.item_id == item.id,
                                                        ConfigVersion.version == previous))
        old.status = "SUPERSEDED"
    v.status = "ACTIVE"
    v.decided_by, v.decided_at, v.decision_comment = ctx.user_id, datetime.now(UTC), comment
    item.active_version = v.version
    item.is_retired = False
    ctx.audit(action="config.version_activated", entity_type="config_item", entity_id=item.id,
              changes={"key": item.key, "version": [previous, v.version]}, reason=comment)


def decide(ctx: TenantContext, version_id: uuid.UUID, approve: bool, comment: str | None) -> ConfigVersion:
    v = get_version(ctx, version_id, for_update=True)
    if v.status != "DRAFT":
        raise ConflictError("Only draft versions can be approved or rejected", code="invalid_status")
    if v.created_by == ctx.user_id:
        raise BusinessRuleError("A configuration change must be approved by a different user",
                                code="segregation_of_duties")
    item = ctx.db.get(ConfigItem, v.item_id)
    if approve:
        _activate(ctx, item, v, comment)
    else:
        if not comment:
            raise BusinessRuleError("A reason is required to reject a change", code="comment_required")
        v.status = "REJECTED"
        v.decided_by, v.decided_at, v.decision_comment = ctx.user_id, datetime.now(UTC), comment
        ctx.audit(action="config.version_rejected", entity_type="config_item", entity_id=item.id,
                  changes={"key": item.key, "version": v.version}, reason=comment)
    ctx.db.commit()
    return v


def retire(ctx: TenantContext, item_id: uuid.UUID, reason: str) -> ConfigItem:
    item = get_item(ctx, item_id)
    if item.is_retired:
        raise ConflictError("Already retired", code="invalid_status")
    item.is_retired = True
    ctx.audit(action="config.item_retired", entity_type="config_item", entity_id=item.id,
              changes={"key": item.key, "version": item.active_version}, reason=reason)
    ctx.db.commit()
    return item


def list_items(ctx: TenantContext, kind: str | None, entity_type: str | None) -> list[dict]:
    stmt = select(ConfigItem).where(ConfigItem.organization_id == ctx.organization_id)
    if kind:
        stmt = stmt.where(ConfigItem.kind == kind)
    if entity_type:
        stmt = stmt.where(ConfigItem.entity_type == entity_type)
    out = []
    for item in ctx.db.scalars(stmt.order_by(ConfigItem.kind, ConfigItem.key)):
        versions = list(ctx.db.scalars(select(ConfigVersion).where(ConfigVersion.item_id == item.id)
                                       .order_by(ConfigVersion.version.desc())))
        active = next((v for v in versions if v.version == item.active_version), None)
        out.append({"item": item, "active": active, "draft": next((v for v in versions if v.status == "DRAFT"), None),
                    "version_count": len(versions)})
    return out


def versions(ctx: TenantContext, item_id: uuid.UUID) -> list[ConfigVersion]:
    get_item(ctx, item_id)
    return list(ctx.db.scalars(select(ConfigVersion).where(ConfigVersion.item_id == item_id)
                               .order_by(ConfigVersion.version.desc())))


# ---------------------------------------------------------------- custom fields

def field_definitions(ctx: TenantContext, entity_type: str) -> list[dict]:
    out = [v.definition | {"version": v.version} for _i, v in active_definitions(ctx, "CUSTOM_FIELD", entity_type)]
    return sorted(out, key=lambda d: (d.get("order", 0), d["key"]))


def _visible(d: dict, values: dict) -> bool:
    cond = d.get("visible_when")
    if not cond:
        return True
    current = values.get(cond["field"])
    return current in cond["equals"] if isinstance(cond["equals"], list) else current == cond["equals"]


def _coerce(d: dict, value: Any) -> Any:
    t = d["field_type"]
    if t == "TEXT":
        if not isinstance(value, str):
            raise ValueError("must be text")
        value = value.strip()
        if d.get("max_length") and len(value) > d["max_length"]:
            raise ValueError(f"must be at most {d['max_length']} characters")
        pattern = defs.TEXT_FORMATS[d.get("text_format", "ANY")]
        if pattern is not None and not pattern.match(value):
            raise ValueError(f"must match the format {d['text_format']}")
        return value
    if t == "NUMBER":
        if isinstance(value, bool):
            raise ValueError("must be a number")
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValueError("must be a number")
        if d.get("min_value") is not None and num < d["min_value"]:
            raise ValueError(f"must be >= {d['min_value']}")
        if d.get("max_value") is not None and num > d["max_value"]:
            raise ValueError(f"must be <= {d['max_value']}")
        return num
    if t == "DATE":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise ValueError("must be a date (YYYY-MM-DD)")
    if t == "BOOLEAN":
        if not isinstance(value, bool):
            raise ValueError("must be true or false")
        return value
    if t == "LIST":
        if value not in d["options"]:
            raise ValueError(f"must be one of {d['options']}")
        return value
    if t == "MULTISELECT":
        if not isinstance(value, list) or any(v not in d["options"] for v in value):
            raise ValueError(f"must be a list of {d['options']}")
        return sorted(set(value), key=d["options"].index)
    raise ValueError("unsupported field type")


def field_values(ctx: TenantContext, entity_type: str, entity_id: uuid.UUID) -> dict:
    return {r.field_key: r.value for r in ctx.db.scalars(select(CustomFieldValue).where(
        CustomFieldValue.organization_id == ctx.organization_id, CustomFieldValue.entity_type == entity_type,
        CustomFieldValue.entity_id == entity_id))}


def apply_values(ctx: TenantContext, entity_type: str, entity_id: uuid.UUID | None, values: dict | None,
                 *, creating: bool = False) -> dict:
    """Validate and store custom field values in the current transaction (no commit).

    Partial updates merge with stored values; ``None`` clears a value. Required fields
    are enforced on the merged result, considering conditional visibility. With
    ``entity_id=None`` the values are only validated (call it before creating a record).
    """
    definitions = {d["key"]: d for d in field_definitions(ctx, entity_type)}
    values = values or {}
    errors = {k: "unknown custom field" for k in values if k not in definitions}
    current = {} if creating or entity_id is None else field_values(ctx, entity_type, entity_id)
    merged = dict(current)
    normalized: dict[str, Any] = {}
    for k, raw in values.items():
        if k not in definitions:
            continue
        if raw is None or raw == "" or raw == []:
            merged.pop(k, None)
            normalized[k] = None
            continue
        try:
            normalized[k] = merged[k] = _coerce(definitions[k], raw)
        except ValueError as exc:
            errors[k] = str(exc)
    for k, d in definitions.items():
        if d.get("required") and _visible(d, merged) and merged.get(k) in (None, "", []):
            errors.setdefault(k, "is required")
    if errors:
        raise BusinessRuleError("Custom field values are not valid", code="invalid_custom_fields", details=errors)
    if entity_id is None:
        return merged
    changes = {}
    for k, v in normalized.items():
        row = ctx.db.scalar(select(CustomFieldValue).where(
            CustomFieldValue.organization_id == ctx.organization_id, CustomFieldValue.entity_type == entity_type,
            CustomFieldValue.entity_id == entity_id, CustomFieldValue.field_key == k))
        before = row.value if row else None
        if before == v:
            continue
        changes[k] = [before, v]
        if v is None:
            ctx.db.delete(row)
        elif row is None:
            ctx.db.add(CustomFieldValue(organization_id=ctx.organization_id, entity_type=entity_type,
                                        entity_id=entity_id, field_key=k, value=v,
                                        field_version=definitions[k]["version"], updated_by=ctx.user_id))
        else:
            row.value, row.field_version, row.updated_by = v, definitions[k]["version"], ctx.user_id
    if changes:
        ctx.audit(action="custom_fields.updated", entity_type=entity_type, entity_id=entity_id, changes=changes)
    return merged


def ensure_field_entity_access(ctx: TenantContext, entity_type: str, entity_id: uuid.UUID, *, write: bool) -> None:
    from app.modules.documents import service as documents  # documents keeps the record loaders

    ent = registry.FIELD_ENTITIES.get(entity_type)
    if ent is None:
        raise BusinessRuleError("Unsupported entity type", code="invalid_entity_type",
                                details={"allowed": sorted(registry.FIELD_ENTITIES)})
    ctx.ensure(ent.read_permission)
    documents.check_access(ctx, entity_type, entity_id, write=False)
    if write:
        ctx.ensure(ent.write_permission)


# ---------------------------------------------------------------- approval matrix

def ensure_approval(ctx: TenantContext, entity_type: str, action: str, *, plant_id: uuid.UUID | None = None,
                    gage_type_id: uuid.UUID | None = None) -> None:
    """Apply the organization's approval matrix (if any) on top of RBAC permissions."""
    found = active_definition(ctx, "APPROVAL_MATRIX", entity_type)
    if not found:
        return
    version, matrix = found
    rule = matrix["actions"].get(action)
    if not rule:
        return
    role = ctx.membership.role.code
    if rule.get("roles") and role not in rule["roles"]:
        raise PermissionDeniedError(
            f"The approval matrix does not allow role '{role}' to {action.lower()} this record",
            code="approval_matrix_denied",
            details={"entity_type": entity_type, "action": action, "allowed_roles": rule["roles"],
                     "matrix_version": version})
    if rule.get("authorization"):
        competency.ensure_authorized(ctx, ctx.user_id, rule["authorization"], plant_id=plant_id,
                                     gage_type_id=gage_type_id)


# ---------------------------------------------------------------- business rules

def _holds(cond: dict, facts: dict) -> bool:
    v, op, target = facts.get(cond["fact"]), cond["op"], cond.get("value")
    if op == "is_empty":
        return v in (None, "", [], 0, False)
    if op == "not_empty":
        return v not in (None, "", [], 0, False)
    if op == "eq":
        return v == target
    if op == "ne":
        return v != target
    if op == "in":
        return v in target
    if op == "not_in":
        return v not in target
    if v is None:
        return False
    return {"gt": v > target, "gte": v >= target, "lt": v < target, "lte": v <= target}[op]


def evaluate_rules(ctx: TenantContext, entity_type: str, transition: str, facts: dict) -> tuple[list[dict], list[dict]]:
    """Return (blocking, warning) rule failures for a transition."""
    blocks, warns = [], []
    for item, v in active_definitions(ctx, "BUSINESS_RULE", entity_type):
        rule = v.definition
        if "*" not in rule["transitions"] and transition not in rule["transitions"]:
            continue
        results = [_holds(c, facts) for c in rule["conditions"]]
        ok = all(results) if rule["match"] == "all" else any(results)
        if not ok:
            failure = {"rule": rule["name"], "message": rule["message"], "version": v.version}
            (blocks if rule["effect"] == "BLOCK" else warns).append(failure)
    return blocks, warns
