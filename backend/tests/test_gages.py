"""Gage Management: CRUD, search/filters, status rules and authorization of releases."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.conftest import today


@pytest.fixture()
def org(make_org, gage_type, add_user):
    admin = make_org("Gages")
    admin.type_id = gage_type(admin, "CAL", 365)["id"]
    admin.manager = add_user(admin, "metrology_manager")
    admin.tech = add_user(admin, "metrology_technician")
    return admin


def _days_ago(n):
    return (today() - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------- create / read


def test_create_full_gage_record(org, new_gage):
    dept = org.post("/api/v1/departments", json={"plant_id": org.plant_id, "code": "QA", "name": "Quality"}).json()
    g = new_gage(
        org.tech, org.type_id, "cal-0001",
        department_id=dept["id"], manufacturer="Mitutoyo", model="500-196-30", serial_number="SN123",
        range_min="0", range_max="150", unit="mm", resolution="0.01", accuracy="±0.02 mm",
        criticality="HIGH", location="Line 3 / Cell 2", responsible_user_id=org.tech.user_id,
        last_calibration_date=_days_ago(10),
    )
    assert g["gage_code"] == "CAL-0001"  # normalized
    assert g["calibration_frequency_days"] == 365  # from gage type default
    assert g["next_due_date"] == (today() - timedelta(days=10) + timedelta(days=365)).isoformat()
    assert g["status"] == "CALIBRATED" and g["available_for_use"] is True
    assert g["department"]["code"] == "QA" and g["responsible"]["full_name"] == "metrology_technician user"
    assert g["resolution"] == "0.01" and g["range_max"] == "150" and g["accuracy"] == "±0.02 mm"
    fetched = org.get(f"/api/v1/gages/{g['id']}").json()
    assert fetched["serial_number"] == "SN123"


def test_gage_without_calibration_is_overdue_and_unavailable(org, new_gage):
    g = new_gage(org, org.type_id)
    assert g["status"] == "OVERDUE" and g["available_for_use"] is False and g["next_due_date"] is None


def test_due_soon_uses_organization_window(org, new_gage):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(350))  # due in 15 days
    assert g["status"] == "DUE_SOON" and g["days_to_due"] == 15
    org.patch("/api/v1/organization", json={"due_soon_days": 10})
    assert org.get(f"/api/v1/gages/{g['id']}").json()["status"] == "CALIBRATED"


def test_duplicate_gage_code_case_insensitive(org, new_gage):
    new_gage(org, org.type_id, "DUP-1")
    r = org.post("/api/v1/gages", json={"gage_code": "dup-1", "description": "Other", "gage_type_id": org.type_id,
                                        "plant_id": org.plant_id})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_gage_code"


def test_create_validations(org, gage_type):
    no_default = gage_type(org, "NODEF", None)["id"]
    base = {"gage_code": "V-1", "description": "Gage", "plant_id": org.plant_id}
    r = org.post("/api/v1/gages", json=base | {"gage_type_id": no_default})
    assert r.status_code == 422 and r.json()["error"]["code"] == "frequency_required"
    r = org.post("/api/v1/gages", json=base | {"gage_type_id": org.type_id, "range_min": 10, "range_max": 1})
    assert r.status_code == 422
    r = org.post("/api/v1/gages", json=base | {"gage_type_id": org.type_id,
                                               "last_calibration_date": (today() + timedelta(days=1)).isoformat()})
    assert r.status_code == 422 and r.json()["error"]["code"] == "future_last_calibration_date"
    r = org.post("/api/v1/gages", json=base | {"gage_type_id": org.type_id, "gage_code": "bad code!"})
    assert r.status_code == 422
    other_plant = org.post("/api/v1/plants", json={"code": "P2", "name": "Plant 2"}).json()
    dept = org.post("/api/v1/departments", json={"plant_id": other_plant["id"], "code": "QA", "name": "QA"}).json()
    r = org.post("/api/v1/gages", json=base | {"gage_type_id": org.type_id, "department_id": dept["id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "department_plant_mismatch"


def test_inactive_gage_type_cannot_be_used_for_new_gages(org):
    org.patch(f"/api/v1/gage-types/{org.type_id}", json={"is_active": False})
    r = org.post("/api/v1/gages", json={"gage_code": "T-1", "description": "Gage", "gage_type_id": org.type_id,
                                        "plant_id": org.plant_id, "calibration_frequency_days": 30})
    assert r.status_code == 422 and r.json()["error"]["code"] == "gage_type_inactive"


# ---------------------------------------------------------------- list / search / filter


def test_search_filter_sort_and_paginate(org, new_gage, gage_type):
    mic = gage_type(org, "MIC", 180)["id"]
    new_gage(org, org.type_id, "C-1", manufacturer="Mitutoyo", last_calibration_date=_days_ago(1))
    new_gage(org, org.type_id, "C-2", serial_number="XYZ-77", last_calibration_date=_days_ago(360))
    new_gage(org, mic, "M-1")
    oos = new_gage(org, mic, "M-2", last_calibration_date=_days_ago(1))
    org.post(f"/api/v1/gages/{oos['id']}/transitions", json={"target": "OUT_OF_SERVICE", "reason": "Damaged jaw"})

    codes = lambda r: [g["gage_code"] for g in r.json()["items"]]  # noqa: E731
    assert codes(org.get("/api/v1/gages?q=mitu")) == ["C-1"]
    assert codes(org.get("/api/v1/gages?q=xyz-77")) == ["C-2"]
    assert codes(org.get("/api/v1/gages?status=OVERDUE")) == ["M-1"]
    assert codes(org.get("/api/v1/gages?status=DUE_SOON&status=OUT_OF_SERVICE")) == ["C-2", "M-2"]
    assert codes(org.get(f"/api/v1/gages?gage_type_id={mic}")) == ["M-1", "M-2"]
    assert codes(org.get("/api/v1/gages?available=true")) == ["C-1", "C-2"]
    assert codes(org.get("/api/v1/gages?available=false")) == ["M-1", "M-2"]
    assert codes(org.get("/api/v1/gages?sort=-gage_code")) == ["M-2", "M-1", "C-2", "C-1"]
    page = org.get("/api/v1/gages?page=2&page_size=3").json()
    assert page["total"] == 4 and [g["gage_code"] for g in page["items"]] == ["M-2"]
    assert org.get("/api/v1/gages?sort=password").status_code == 422
    assert org.get("/api/v1/gages?status=BROKEN").status_code == 422


# ---------------------------------------------------------------- update


def test_edit_descriptive_fields_is_audited(org, new_gage):
    g = new_gage(org.tech, org.type_id)
    r = org.tech.patch(f"/api/v1/gages/{g['id']}", json={"notes": "Jaws checked", "manufacturer": "Starrett"})
    assert r.status_code == 200 and r.json()["manufacturer"] == "Starrett"
    events = org.get(f"/api/v1/gages/{g['id']}/audit").json()["items"]
    upd = next(e for e in events if e["action"] == "gage.updated")
    assert upd["changes"]["manufacturer"] == [None, "Starrett"]
    assert upd["actor_name"] == "metrology_technician user"


def test_gage_code_and_status_cannot_be_patched(org, new_gage):
    g = new_gage(org, org.type_id)
    assert org.patch(f"/api/v1/gages/{g['id']}", json={"gage_code": "NEW"}).status_code == 422
    assert org.patch(f"/api/v1/gages/{g['id']}", json={"control_status": "ACTIVE"}).status_code == 422
    r = org.patch(f"/api/v1/gages/{g['id']}", json={"description": None})
    assert r.status_code == 422 and r.json()["error"]["code"] == "required_field"


def test_calibration_date_cannot_be_edited_after_registration(org, new_gage):
    """After registration the last calibration only changes through a released calibration activity."""
    g = new_gage(org, org.type_id)  # OVERDUE: no calibration on record
    for actor in (org.tech, org.manager, org):
        r = actor.patch(f"/api/v1/gages/{g['id']}", json={"last_calibration_date": _days_ago(5)})
        assert r.status_code == 422 and r.json()["error"]["details"][0]["type"] == "extra_forbidden"
    assert org.get(f"/api/v1/gages/{g['id']}").json()["status"] == "OVERDUE"


def test_frequency_change_requires_release_and_moves_due_date(org, new_gage):
    g = new_gage(org.tech, org.type_id, last_calibration_date=_days_ago(100))  # due in 265 days
    r = org.tech.patch(f"/api/v1/gages/{g['id']}", json={"calibration_frequency_days": 90})
    assert r.status_code == 403 and r.json()["error"]["details"]["required_permission"] == "gages:release"
    r = org.manager.patch(f"/api/v1/gages/{g['id']}", json={"calibration_frequency_days": 90})
    assert r.status_code == 200 and r.json()["status"] == "OVERDUE"
    upd = next(e for e in org.get(f"/api/v1/gages/{g['id']}/audit").json()["items"] if e["action"] == "gage.updated")
    assert upd["changes"]["status"] == ["CALIBRATED", "OVERDUE"]


def test_resending_unchanged_due_fields_does_not_need_release(org, new_gage):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(5))
    r = org.tech.patch(f"/api/v1/gages/{g['id']}", json={
        "calibration_frequency_days": 365, "notes": "Crib",
    })
    assert r.status_code == 200


# ---------------------------------------------------------------- status transitions


def _transition(actor, gid, target, reason="Reason given", **extra):
    return actor.post(f"/api/v1/gages/{gid}/transitions", json={"target": target, "reason": reason} | extra)


def test_restricted_gage_cannot_be_released_without_authorization(org, new_gage):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(5))
    r = _transition(org.tech, g["id"], "OUT_OF_SERVICE", "Dropped on floor")
    assert r.status_code == 200 and r.json()["status"] == "OUT_OF_SERVICE" and not r.json()["available_for_use"]

    r = _transition(org.tech, g["id"], "ACTIVE", "Looks fine")
    assert r.status_code == 403 and r.json()["error"]["details"]["required_permission"] == "gages:release"
    # A descriptive edit cannot sneak the gage back into service either.
    org.tech.patch(f"/api/v1/gages/{g['id']}", json={"notes": "inspected"})
    assert org.get(f"/api/v1/gages/{g['id']}").json()["status"] == "OUT_OF_SERVICE"

    r = _transition(org.manager, g["id"], "ACTIVE", "Verified after repair")
    assert r.status_code == 200 and r.json()["status"] == "CALIBRATED"


def test_release_does_not_bypass_due_date(org, new_gage):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(400))  # overdue
    _transition(org, g["id"], "OUT_OF_SERVICE")
    r = _transition(org.manager, g["id"], "ACTIVE", "Repaired")
    assert r.json()["status"] == "OVERDUE" and r.json()["available_for_use"] is False


def test_manual_release_cannot_record_a_calibration(org, new_gage):
    """The interim calibration_date of the first increment was removed: calibrations are activities now."""
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(400))
    assert _transition(org.tech, g["id"], "IN_CALIBRATION", "Sent to lab").json()["status"] == "IN_CALIBRATION"
    r = _transition(org.manager, g["id"], "ACTIVE", "Calibrated", calibration_date=_days_ago(1))
    assert r.status_code == 422
    r = _transition(org.manager, g["id"], "ACTIVE", "Back from lab without record")
    assert r.status_code == 200 and r.json()["status"] == "OVERDUE"  # still overdue: nothing was calibrated


def test_invalid_transition_and_missing_reason(org, new_gage):
    g = new_gage(org, org.type_id)
    r = _transition(org, g["id"], "ACTIVE")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_transition"
    r = org.post(f"/api/v1/gages/{g['id']}/transitions", json={"target": "OUT_OF_SERVICE"})
    assert r.status_code == 422


def test_logical_deletion_and_reactivation(org, new_gage):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(5))
    assert _transition(org.tech, g["id"], "INACTIVE", "Scrap").status_code == 403
    r = _transition(org.manager, g["id"], "INACTIVE", "Worn out, scrapped")
    assert r.status_code == 200 and r.json()["status"] == "INACTIVE" and r.json()["retired_at"]

    assert org.get("/api/v1/gages").json()["total"] == 0
    assert org.get("/api/v1/gages?include_inactive=true").json()["total"] == 1
    assert org.get("/api/v1/gages?status=INACTIVE").json()["total"] == 1
    assert org.get(f"/api/v1/gages/{g['id']}").status_code == 200  # record is kept
    r = org.patch(f"/api/v1/gages/{g['id']}", json={"notes": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "gage_inactive"
    assert _transition(org, g["id"], "OUT_OF_SERVICE").json()["error"]["code"] == "invalid_transition"

    r = _transition(org.manager, g["id"], "ACTIVE", "Back in use")
    assert r.json()["status"] == "CALIBRATED" and r.json()["retired_at"] is None


def test_status_history_and_audit_trail(org, new_gage, db):
    g = new_gage(org, org.type_id, last_calibration_date=_days_ago(5))
    _transition(org.tech, g["id"], "OUT_OF_SERVICE", "Damaged")
    _transition(org.manager, g["id"], "ACTIVE", "Repaired and verified")
    hist = org.get(f"/api/v1/gages/{g['id']}/status-history").json()
    assert [(h["from_status"], h["to_status"]) for h in hist] == [
        ("OUT_OF_SERVICE", "CALIBRATED"), ("CALIBRATED", "OUT_OF_SERVICE"), (None, "CALIBRATED"),
    ]
    assert hist[0]["reason"] == "Repaired and verified" and hist[0]["changed_by_name"] == "metrology_manager user"
    actions = [e["action"] for e in org.get(f"/api/v1/gages/{g['id']}/audit").json()["items"]]
    assert actions == ["gage.released", "gage.restricted", "gage.created"]

    with pytest.raises(Exception, match="append-only"):
        with db.begin_nested():
            db.execute(text("DELETE FROM gage_status_history WHERE gage_id = :g"), {"g": g["id"]})


def test_dashboard_summary_counts_live_data(org, new_gage):
    new_gage(org, org.type_id, "D-1", last_calibration_date=_days_ago(1))
    new_gage(org, org.type_id, "D-2", last_calibration_date=_days_ago(355))
    new_gage(org, org.type_id, "D-3")
    retired = new_gage(org, org.type_id, "D-4")
    _transition(org, retired["id"], "INACTIVE", "Scrapped")
    s = org.get("/api/v1/dashboard/summary").json()
    assert s["by_status"]["CALIBRATED"] == 1 and s["by_status"]["DUE_SOON"] == 1
    assert s["by_status"]["OVERDUE"] == 1 and s["by_status"]["INACTIVE"] == 1
    assert s["total_in_service"] == 3 and s["available"] == 2
    assert [g["gage_code"] for g in s["upcoming"]] == ["D-3", "D-2"]
    assert s["as_of"] == today().isoformat()


def test_empty_dashboard_has_zero_counts(make_org):
    admin = make_org("Empty")
    s = admin.get("/api/v1/dashboard/summary").json()
    assert s["total_in_service"] == 0 and s["upcoming"] == [] and set(s["by_status"].values()) == {0}
