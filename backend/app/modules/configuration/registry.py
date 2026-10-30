"""What each business module exposes to the configuration layer.

Modules register:

* custom-field entities (record types that accept custom fields, with their built-in
  field names so forms can mix both);
* workflow entities: the default workflow, the states the domain logic depends on, the
  capabilities a state may grant, the facts business rules may test, and an adapter
  that reads/writes the entity's state.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

APPROVAL_ACTIONS = ("REVIEW", "APPROVE", "RELEASE", "REJECT", "CANCEL")
# Records whose sensitive actions can be restricted by an approval matrix.
APPROVAL_ENTITIES = ("calibration", "msa_study", "oot_case")


@dataclass(frozen=True)
class FieldEntity:
    entity_type: str
    read_permission: str
    write_permission: str
    builtin_fields: tuple[str, ...]


@dataclass
class WorkflowEntity:
    entity_type: str
    default_definition: dict
    # State code -> "initial" | "terminal" | "state": must exist in every custom definition.
    system_states: dict[str, str]
    capabilities: tuple[str, ...]
    # Fact name -> "number" | "boolean" | "text".
    facts: dict[str, str]
    # Adapter (set by the owning module).
    load: Callable[[Any, uuid.UUID], Any] = field(repr=False, default=None)        # (ctx, id) -> entity
    get_state: Callable[[Any], str] = field(repr=False, default=None)
    set_state: Callable[[Any, Any, str], None] = field(repr=False, default=None)  # (ctx, entity, state)
    get_version: Callable[[Any], int] = field(repr=False, default=None)
    compute_facts: Callable[[Any, Any], dict] = field(repr=False, default=None)   # (ctx, entity)
    # Users that segregation rules refer to: {"responsible": id, "created_by": id, ...}
    parties: Callable[[Any], dict] = field(repr=False, default=None)
    # Optional domain checks before entering a state (raise to block) and hooks after.
    before_enter: Callable[[Any, Any, str], None] | None = field(repr=False, default=None)
    after_enter: Callable[[Any, Any, str, str], None] | None = field(repr=False, default=None)
    plant_of: Callable[[Any], uuid.UUID | None] = field(repr=False, default=None)
    link_prefix: str = "/"


FIELD_ENTITIES: dict[str, FieldEntity] = {}
WORKFLOW_ENTITIES: dict[str, WorkflowEntity] = {}


def register_field_entity(entity: FieldEntity) -> None:
    FIELD_ENTITIES[entity.entity_type] = entity


def register_workflow_entity(entity: WorkflowEntity) -> None:
    WORKFLOW_ENTITIES[entity.entity_type] = entity
