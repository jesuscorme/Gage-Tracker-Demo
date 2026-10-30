"""Gage status rules.

A gage has two layers of status:

* **Controlled status** (stored, changed only through authorized transitions):
  ``ACTIVE``, ``OUT_OF_SERVICE``, ``IN_CALIBRATION``, ``INACTIVE``.
* **Effective status** (what users see). When the controlled status is not ``ACTIVE``
  it wins. Otherwise it is derived from the due date and the organization's
  "due soon" window:

  ===========================================  ==============
  Condition (ACTIVE gage)                      Status
  ===========================================  ==============
  no calibration date on record                OVERDUE
  next_due_date < today                        OVERDUE
  today <= next_due_date <= today + window     DUE_SOON
  next_due_date > today + window               CALIBRATED
  ===========================================  ==============

  The due date is the last valid day: a gage due today is still usable (DUE_SOON).

Only CALIBRATED and DUE_SOON gages are available for normal use.

The same rules exist as a Python function (single gage) and as a SQL expression
(filtering/counting). ``tests/test_gage_status.py`` checks they agree.
"""

from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import ColumnElement, case, literal

from app.modules.identity.permissions import P


class ControlStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    IN_CALIBRATION = "IN_CALIBRATION"
    INACTIVE = "INACTIVE"


class GageStatus(StrEnum):
    CALIBRATED = "CALIBRATED"
    DUE_SOON = "DUE_SOON"
    OVERDUE = "OVERDUE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    IN_CALIBRATION = "IN_CALIBRATION"
    INACTIVE = "INACTIVE"


AVAILABLE_STATUSES = frozenset({GageStatus.CALIBRATED, GageStatus.DUE_SOON})


def next_due(last_calibration: date | None, frequency_days: int) -> date | None:
    return last_calibration + timedelta(days=frequency_days) if last_calibration else None


def effective_status(
    control_status: str, next_due_date: date | None, today: date, due_soon_days: int
) -> GageStatus:
    if control_status != ControlStatus.ACTIVE:
        return GageStatus(control_status)
    if next_due_date is None or next_due_date < today:
        return GageStatus.OVERDUE
    if next_due_date <= today + timedelta(days=due_soon_days):
        return GageStatus.DUE_SOON
    return GageStatus.CALIBRATED


def effective_status_sql(control_col, due_col, today: date, due_soon_days: int) -> ColumnElement[str]:
    soon_limit = today + timedelta(days=due_soon_days)
    return case(
        (control_col != ControlStatus.ACTIVE.value, control_col),
        (due_col.is_(None), literal(GageStatus.OVERDUE.value)),
        (due_col < today, literal(GageStatus.OVERDUE.value)),
        (due_col <= soon_limit, literal(GageStatus.DUE_SOON.value)),
        else_=literal(GageStatus.CALIBRATED.value),
    )


# Allowed controlled-status transitions and the permission each one requires.
# Releasing a restriction is deliberately a different permission from imposing it, so a
# user able to block a gage cannot put it back into service on their own.
TRANSITIONS: dict[tuple[ControlStatus, ControlStatus], str] = {
    (ControlStatus.ACTIVE, ControlStatus.OUT_OF_SERVICE): P.GAGES_RESTRICT,
    (ControlStatus.ACTIVE, ControlStatus.IN_CALIBRATION): P.GAGES_RESTRICT,
    (ControlStatus.IN_CALIBRATION, ControlStatus.OUT_OF_SERVICE): P.GAGES_RESTRICT,
    (ControlStatus.OUT_OF_SERVICE, ControlStatus.IN_CALIBRATION): P.GAGES_RESTRICT,
    (ControlStatus.OUT_OF_SERVICE, ControlStatus.ACTIVE): P.GAGES_RELEASE,
    (ControlStatus.IN_CALIBRATION, ControlStatus.ACTIVE): P.GAGES_RELEASE,
    (ControlStatus.ACTIVE, ControlStatus.INACTIVE): P.GAGES_RETIRE,
    (ControlStatus.OUT_OF_SERVICE, ControlStatus.INACTIVE): P.GAGES_RETIRE,
    (ControlStatus.IN_CALIBRATION, ControlStatus.INACTIVE): P.GAGES_RETIRE,
    (ControlStatus.INACTIVE, ControlStatus.ACTIVE): P.GAGES_RELEASE,
}


def transition_permission(current: ControlStatus, target: ControlStatus) -> str | None:
    """Permission needed for ``current -> target``, or None if the transition is not allowed."""
    return TRANSITIONS.get((current, target))
