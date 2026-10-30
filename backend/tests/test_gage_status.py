"""Unit tests of the status rules, and agreement between the Python and SQL versions."""

from datetime import date, timedelta

import pytest
from sqlalchemy import Date, String, literal, select

from app.modules.gages.status import (
    TRANSITIONS,
    ControlStatus,
    GageStatus,
    effective_status,
    effective_status_sql,
    next_due,
    transition_permission,
)
from app.modules.identity.permissions import P

TODAY = date(2026, 10, 29)
WINDOW = 30

CASES = [
    # (control, days from today to due date or None, expected)
    ("ACTIVE", None, GageStatus.OVERDUE),
    ("ACTIVE", -1, GageStatus.OVERDUE),
    ("ACTIVE", 0, GageStatus.DUE_SOON),
    ("ACTIVE", WINDOW, GageStatus.DUE_SOON),
    ("ACTIVE", WINDOW + 1, GageStatus.CALIBRATED),
    ("OUT_OF_SERVICE", 200, GageStatus.OUT_OF_SERVICE),
    ("IN_CALIBRATION", -10, GageStatus.IN_CALIBRATION),
    ("INACTIVE", 200, GageStatus.INACTIVE),
]


@pytest.mark.parametrize("control,offset,expected", CASES)
def test_effective_status(control, offset, expected):
    due = TODAY + timedelta(days=offset) if offset is not None else None
    assert effective_status(control, due, TODAY, WINDOW) == expected


@pytest.mark.parametrize("control,offset,expected", CASES)
def test_sql_expression_matches_python(db, control, offset, expected):
    due = TODAY + timedelta(days=offset) if offset is not None else None
    expr = effective_status_sql(literal(control, String), literal(due, Date), TODAY, WINDOW)
    assert db.scalar(select(expr)) == expected.value


def test_zero_window_means_due_soon_only_on_due_date():
    assert effective_status("ACTIVE", TODAY, TODAY, 0) == GageStatus.DUE_SOON
    assert effective_status("ACTIVE", TODAY + timedelta(days=1), TODAY, 0) == GageStatus.CALIBRATED


def test_next_due():
    assert next_due(date(2026, 1, 1), 365) == date(2027, 1, 1)
    assert next_due(None, 365) is None


def test_release_and_restrict_require_different_permissions():
    restrict = {k for k, v in TRANSITIONS.items() if v == P.GAGES_RESTRICT}
    release = {k for k, v in TRANSITIONS.items() if v == P.GAGES_RELEASE}
    assert all(target != ControlStatus.ACTIVE for _, target in restrict)
    assert all(target == ControlStatus.ACTIVE for _, target in release)


def test_disallowed_transitions():
    assert transition_permission(ControlStatus.INACTIVE, ControlStatus.OUT_OF_SERVICE) is None
    assert transition_permission(ControlStatus.ACTIVE, ControlStatus.ACTIVE) is None
    assert transition_permission(ControlStatus.INACTIVE, ControlStatus.IN_CALIBRATION) is None
