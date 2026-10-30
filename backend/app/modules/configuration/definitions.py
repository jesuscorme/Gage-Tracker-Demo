"""Schemas of each configuration kind and their semantic validation.

Definitions are declarative data only. Nothing in a definition is ever executed: rule
conditions are compared with a fixed set of operators, and text formats are chosen from
a fixed list (no user-supplied regular expressions).
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.errors import BusinessRuleError
from app.modules.competency.models import ACTIVITIES
from app.modules.configuration import registry
from app.modules.identity.permissions import PERMISSIONS, SYSTEM_ROLES

KEY = r"^[a-z][a-z0-9_]{1,59}$"
CODE = r"^[A-Z][A-Z0-9_]{1,39}$"
FIELD_TYPES = ("TEXT", "NUMBER", "DATE", "LIST", "MULTISELECT", "BOOLEAN")
TEXT_FORMATS = {
    "ANY": None,
    "ALPHANUMERIC": re.compile(r"^[A-Za-z0-9]*$"),
    "UPPERCASE_CODE": re.compile(r"^[A-Z0-9][A-Z0-9_.\-/]*$"),
    "DIGITS": re.compile(r"^[0-9]*$"),
    "EMAIL": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
}
OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "is_empty", "not_empty")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- custom fields and forms

class VisibleWhen(Strict):
    field: str = Field(pattern=KEY)
    equals: Any


class CustomFieldDef(Strict):
    entity_type: str
    key: str = Field(pattern=KEY)
    label: str = Field(min_length=1, max_length=120)
    field_type: Literal[FIELD_TYPES]  # type: ignore[valid-type]
    required: bool = False
    help_text: str | None = Field(default=None, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=100)
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = Field(default=None, ge=1, le=2000)
    text_format: Literal[tuple(TEXT_FORMATS)] = "ANY"  # type: ignore[valid-type]
    visible_when: VisibleWhen | None = None
    order: int = 0

    @model_validator(mode="after")
    def _check(self):
        if self.field_type in ("LIST", "MULTISELECT"):
            if not self.options or len(set(self.options)) != len(self.options):
                raise ValueError("LIST and MULTISELECT fields need unique options")
        elif self.options:
            raise ValueError("options only apply to LIST and MULTISELECT fields")
        if self.field_type != "NUMBER" and (self.min_value is not None or self.max_value is not None):
            raise ValueError("min_value/max_value only apply to NUMBER fields")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must not exceed max_value")
        if self.field_type != "TEXT" and (self.max_length or self.text_format != "ANY"):
            raise ValueError("max_length/text_format only apply to TEXT fields")
        if self.visible_when and self.visible_when.field == self.key:
            raise ValueError("a field cannot depend on itself")
        return self


class FormSection(Strict):
    title: str = Field(min_length=1, max_length=120)
    fields: list[str] = Field(min_length=1, max_length=60)


class FormDef(Strict):
    entity_type: str
    sections: list[FormSection] = Field(min_length=1, max_length=20)


# ---------------------------------------------------------------- workflows

class StateDef(Strict):
    code: str = Field(pattern=CODE)
    label: str = Field(min_length=1, max_length=80)
    capabilities: list[str] = Field(default_factory=list)


class TransitionDef(Strict):
    code: str = Field(pattern=CODE)
    label: str = Field(min_length=1, max_length=80)
    from_states: list[str] = Field(min_length=1)
    to: str
    permission: str
    action: Literal[("ADVANCE",) + registry.APPROVAL_ACTIONS] = "ADVANCE"  # type: ignore[valid-type]
    authorization: str | None = None
    require_comment: bool = False
    approvals_required: int = Field(default=1, ge=1, le=5)
    # Parties of the record that may not perform this transition (e.g. "responsible").
    segregate_from: list[str] = Field(default_factory=list)
    # Distinct approvers when approvals_required > 1 is implicit.


class EscalationDef(Strict):
    state: str
    after_hours: int = Field(ge=1, le=24 * 90)
    notify_permission: str


class WorkflowDef(Strict):
    entity_type: str
    initial: str
    states: list[StateDef] = Field(min_length=2, max_length=30)
    transitions: list[TransitionDef] = Field(min_length=1, max_length=80)
    escalations: list[EscalationDef] = Field(default_factory=list, max_length=30)


# ---------------------------------------------------------------- approval matrix and rules

class ApprovalRule(Strict):
    roles: list[str] = Field(default_factory=list)
    authorization: str | None = None


class ApprovalMatrixDef(Strict):
    entity_type: str
    actions: dict[str, ApprovalRule]


class Condition(Strict):
    fact: str
    op: Literal[OPERATORS]  # type: ignore[valid-type]
    value: Any = None


class BusinessRuleDef(Strict):
    entity_type: str
    name: str = Field(min_length=3, max_length=120)
    # Transition codes the rule guards ("*" = every transition).
    transitions: list[str] = Field(min_length=1)
    match: Literal["all", "any"] = "all"
    # Conditions that must hold for the transition to proceed.
    conditions: list[Condition] = Field(min_length=1, max_length=20)
    effect: Literal["BLOCK", "WARN"] = "BLOCK"
    message: str = Field(min_length=3, max_length=300)


SCHEMAS = {"CUSTOM_FIELD": CustomFieldDef, "FORM": FormDef, "WORKFLOW": WorkflowDef,
           "APPROVAL_MATRIX": ApprovalMatrixDef, "BUSINESS_RULE": BusinessRuleDef}
NEEDS_APPROVAL = {"WORKFLOW", "APPROVAL_MATRIX", "BUSINESS_RULE"}


def _fail(errors: list[str]):
    if errors:
        raise BusinessRuleError("The configuration is not valid", code="invalid_configuration", details=errors)


def validate_semantics(kind: str, d: BaseModel, *, custom_field_keys: set[str] | None = None) -> None:
    errors: list[str] = []
    if kind in ("CUSTOM_FIELD", "FORM"):
        ent = registry.FIELD_ENTITIES.get(d.entity_type)
        if ent is None:
            _fail([f"entity_type must be one of {sorted(registry.FIELD_ENTITIES)}"])
        if kind == "CUSTOM_FIELD":
            if d.key in ent.builtin_fields:
                errors.append(f"'{d.key}' is a built-in field of {d.entity_type}")
            if d.visible_when and custom_field_keys is not None and d.visible_when.field not in custom_field_keys:
                errors.append(f"visible_when refers to unknown custom field '{d.visible_when.field}'")
        else:
            known = set(ent.builtin_fields) | (custom_field_keys or set())
            seen = set()
            for s in d.sections:
                for f in s.fields:
                    if f not in known:
                        errors.append(f"unknown field '{f}' in section '{s.title}'")
                    if f in seen:
                        errors.append(f"field '{f}' appears more than once")
                    seen.add(f)
    elif kind == "WORKFLOW":
        errors += _validate_workflow(d)
    elif kind == "APPROVAL_MATRIX":
        if d.entity_type not in registry.APPROVAL_ENTITIES:
            errors.append(f"entity_type must be one of {list(registry.APPROVAL_ENTITIES)}")
        for action, rule in d.actions.items():
            if action not in registry.APPROVAL_ACTIONS:
                errors.append(f"unknown action '{action}'")
            for role in rule.roles:
                if role not in SYSTEM_ROLES:
                    errors.append(f"unknown role '{role}'")
            if rule.authorization and rule.authorization not in ACTIVITIES:
                errors.append(f"unknown authorization activity '{rule.authorization}'")
            if not rule.roles and not rule.authorization:
                errors.append(f"action '{action}' must restrict roles and/or require an authorization")
    elif kind == "BUSINESS_RULE":
        ent = registry.WORKFLOW_ENTITIES.get(d.entity_type)
        if ent is None:
            _fail([f"entity_type must be one of {sorted(registry.WORKFLOW_ENTITIES)}"])
        for c in d.conditions:
            ftype = ent.facts.get(c.fact)
            if ftype is None:
                errors.append(f"unknown fact '{c.fact}' (available: {sorted(ent.facts)})")
                continue
            if c.op in ("gt", "gte", "lt", "lte") and (ftype != "number" or not isinstance(c.value, (int, float))
                                                        or isinstance(c.value, bool)):
                errors.append(f"operator {c.op} needs a numeric fact and value ({c.fact})")
            if c.op in ("in", "not_in") and not isinstance(c.value, list):
                errors.append(f"operator {c.op} needs a list value ({c.fact})")
    _fail(errors)


def _validate_workflow(d: WorkflowDef) -> list[str]:
    ent = registry.WORKFLOW_ENTITIES.get(d.entity_type)
    if ent is None:
        return [f"entity_type must be one of {sorted(registry.WORKFLOW_ENTITIES)}"]
    errors = []
    codes = [s.code for s in d.states]
    if len(set(codes)) != len(codes):
        errors.append("state codes must be unique")
    states = set(codes)
    for code, role in ent.system_states.items():
        if code not in states:
            errors.append(f"system state '{code}' is required for {d.entity_type}")
    initial = [c for c, r in ent.system_states.items() if r == "initial"]
    if initial and d.initial != initial[0]:
        errors.append(f"the initial state must be '{initial[0]}'")
    terminal = {c for c, r in ent.system_states.items() if r == "terminal"}
    for s in d.states:
        for cap in s.capabilities:
            if cap not in ent.capabilities:
                errors.append(f"unknown capability '{cap}' in state {s.code}")
    tcodes = [t.code for t in d.transitions]
    if len(set(tcodes)) != len(tcodes):
        errors.append("transition codes must be unique")
    for t in d.transitions:
        for s in t.from_states + [t.to]:
            if s not in states:
                errors.append(f"transition {t.code} refers to unknown state '{s}'")
        if set(t.from_states) & terminal:
            errors.append(f"transition {t.code} leaves a terminal state")
        if t.permission not in PERMISSIONS:
            errors.append(f"transition {t.code}: unknown permission '{t.permission}'")
        if t.authorization and t.authorization not in ACTIVITIES:
            errors.append(f"transition {t.code}: unknown authorization '{t.authorization}'")
        for party in t.segregate_from:
            if party not in ("responsible", "created_by", "previous_actor"):
                errors.append(f"transition {t.code}: unknown party '{party}'")
    for e in d.escalations:
        if e.state not in states:
            errors.append(f"escalation refers to unknown state '{e.state}'")
        if e.notify_permission not in PERMISSIONS:
            errors.append(f"escalation: unknown permission '{e.notify_permission}'")
    # Every state must be reachable from the initial state, and every non-terminal
    # state must have a way out.
    reach, frontier = {d.initial}, [d.initial]
    while frontier:
        cur = frontier.pop()
        for t in d.transitions:
            if cur in t.from_states and t.to not in reach:
                reach.add(t.to)
                frontier.append(t.to)
    for s in states - reach:
        errors.append(f"state '{s}' is not reachable from '{d.initial}'")
    for s in states - terminal:
        if not any(s in t.from_states for t in d.transitions):
            errors.append(f"state '{s}' has no outgoing transition")
    return errors


def parse(kind: str, raw: dict) -> BaseModel:
    try:
        return SCHEMAS[kind].model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in getattr(exc, "errors", lambda: [])()]
        raise BusinessRuleError("The configuration is not valid", code="invalid_configuration",
                                details=details or [str(exc)])


def item_key(kind: str, d: BaseModel) -> str:
    if kind == "CUSTOM_FIELD":
        return f"{d.entity_type}.{d.key}"
    if kind == "BUSINESS_RULE":
        return f"{d.entity_type}.{re.sub(r'[^a-z0-9]+', '_', d.name.lower()).strip('_')}"
    return d.entity_type
