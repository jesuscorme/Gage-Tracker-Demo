"""Calibration Management: full workflow and its rules."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.conftest import PDF, today


def _iso(days=0):
    return (today() + timedelta(days=days)).isoformat()


@pytest.fixture()
def lab(make_org, gage_type, add_user, new_gage, authorize):
    """Organization with a technician, a reviewer and an approver, a valid standard and an overdue gage."""
    admin = make_org("Calibration")
    admin.type_id = gage_type(admin, "CAL", 365)["id"]
    admin.tech = add_user(admin, "metrology_technician")
    admin.reviewer = add_user(admin, "metrology_manager")
    admin.approver = add_user(admin, "metrology_manager")
    authorize(admin, admin.tech.user_id, "INTERNAL_CALIBRATION")
    authorize(admin, admin.tech.user_id, "ROUTINE_VERIFICATION")
    authorize(admin, admin.reviewer.user_id, "TECHNICAL_REVIEW")
    authorize(admin, admin.approver.user_id, "APPROVAL")
    std = admin.post("/api/v1/standards", json={"standard_code": "GB-01", "description": "Gauge blocks",
                                                "category": "GAUGE_BLOCK", "plant_id": admin.plant_id,
                                                "calibration_frequency_days": 365}).json()
    admin.post(f"/api/v1/standards/{std['id']}/certificates",
               data={"certificate_number": "STD-1", "issuer": "CENAM", "calibration_date": _iso(-30),
                     "issue_date": _iso(-30)}, files={"file": ("c.pdf", PDF, "application/pdf")})
    admin.std = std
    admin.gage = new_gage(admin, admin.type_id, "CAL-100", last_calibration_date=_iso(-400))
    return admin


def plan(lab, activity_type="INTERNAL_CALIBRATION", gage=None, **extra):
    r = lab.post("/api/v1/calibrations", json={"gage_id": (gage or lab.gage)["id"], "activity_type": activity_type,
                                               "planned_date": _iso(0)} | extra)
    assert r.status_code == 201, r.text
    return r.json()


def to_in_progress(lab, act, **schedule):
    aid = act["id"]
    assert lab.post(f"/api/v1/calibrations/{aid}/request", json={}).status_code == 200
    body = {"scheduled_date": _iso(0)} | schedule
    if act["activity_type"] != "EXTERNAL_CALIBRATION":
        body.setdefault("technician_id", lab.tech.user_id)
    r = lab.post(f"/api/v1/calibrations/{aid}/schedule", json=body)
    assert r.status_code == 200, r.text
    starter = lab.tech if act["activity_type"] != "EXTERNAL_CALIBRATION" else lab
    r = starter.post(f"/api/v1/calibrations/{aid}/start")
    assert r.status_code == 200, r.text
    return r.json()


def point(actor, aid, phase, measured, nominal="10", lo="9.98", hi="10.02", **extra):
    return actor.post(f"/api/v1/calibrations/{aid}/points", json={
        "phase": phase, "nominal": nominal, "lower_limit": lo, "upper_limit": hi, "measured": measured,
        "unit": "mm", "description": "10 mm block"} | extra)


def capture_internal(lab, aid, as_found="10.01", adjusted=False, as_left=None):
    t = lab.tech
    assert t.patch(f"/api/v1/calibrations/{aid}", json={
        "performed_date": _iso(0), "method": "PR-MET-04 rev 2", "environment_temperature": "20.1",
        "environment_humidity": "45", "adjusted": adjusted}).status_code == 200
    assert point(t, aid, "AS_FOUND", as_found).status_code == 201
    if as_left:
        assert point(t, aid, "AS_LEFT", as_left).status_code == 201
    assert t.post(f"/api/v1/calibrations/{aid}/standards", json={"standard_id": lab.std["id"]}).status_code == 201


def approve_and_release(lab, aid):
    r = lab.reviewer.post(f"/api/v1/calibrations/{aid}/review", json={"accept": True, "comments": "OK"})
    assert r.status_code == 200, r.text
    r = lab.approver.post(f"/api/v1/calibrations/{aid}/approve", json={"accept": True})
    assert r.status_code == 200, r.text
    r = lab.post(f"/api/v1/calibrations/{aid}/release", json={})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- happy paths


def test_internal_calibration_end_to_end_updates_gage(lab):
    act = plan(lab)
    assert act["calibration_code"].startswith(f"CAL-{today().year}-")
    act = to_in_progress(lab, act)
    gage = lab.get(f"/api/v1/gages/{lab.gage['id']}").json()
    assert gage["status"] == "IN_CALIBRATION"

    capture_internal(lab, act["id"])
    r = lab.tech.post(f"/api/v1/calibrations/{act['id']}/submit", json={})
    assert r.status_code == 200 and r.json()["status"] == "PENDING_REVIEW" and r.json()["result"] == "PASS"
    # Reviewer is notified.
    notes = lab.reviewer.get("/api/v1/notifications").json()
    assert notes["unread"] >= 1 and notes["items"][0]["kind"] == "calibration.submitted"

    done = approve_and_release(lab, act["id"])
    assert done["status"] == "RELEASED" and done["due_date"] == _iso(365)
    assert done["reviewer_name"] == "metrology_manager user" and done["approved_at"]
    gage = lab.get(f"/api/v1/gages/{lab.gage['id']}").json()
    assert gage["last_calibration_date"] == _iso(0) and gage["next_due_date"] == _iso(365)
    assert gage["status"] == "CALIBRATED" and gage["available_for_use"]
    hist = lab.get(f"/api/v1/gages/{lab.gage['id']}/status-history").json()
    assert hist[0]["from_status"] == "IN_CALIBRATION" and hist[0]["to_status"] == "CALIBRATED"
    usage = lab.get(f"/api/v1/standards/{lab.std['id']}/usages").json()
    assert usage[0]["calibration_code"] == done["calibration_code"] and usage[0]["standard_status"] == "VALID"
    assert usage[0]["certificate_id"]


def test_as_found_and_as_left_are_separate_and_adjustment_result(lab):
    act = to_in_progress(lab, plan(lab))
    aid = act["id"]
    # As Left without adjustment is refused.
    lab.tech.patch(f"/api/v1/calibrations/{aid}", json={"performed_date": _iso(0), "method": "PR-1",
                                                        "environment_temperature": "20"})
    assert point(lab.tech, aid, "AS_LEFT", "10.00").json()["error"]["code"] == "as_left_without_adjustment"
    capture_internal(lab, aid, as_found="10.05", adjusted=True, as_left="10.00")
    detail = lab.get(f"/api/v1/calibrations/{aid}").json()
    phases = {(p["phase"], p["in_tolerance"]) for p in detail["points"]}
    assert phases == {("AS_FOUND", False), ("AS_LEFT", True)}
    assert detail["computed_result"] == "PASS_AFTER_ADJUSTMENT"
    lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    done = approve_and_release(lab, aid)
    assert done["result"] == "PASS_AFTER_ADJUSTMENT" and done["as_found_in_tolerance"] is False


def test_point_corrections_supersede_and_rows_are_immutable(lab, db):
    aid = to_in_progress(lab, plan(lab))["id"]
    lab.tech.patch(f"/api/v1/calibrations/{aid}", json={"performed_date": _iso(0)})
    first = point(lab.tech, aid, "AS_FOUND", "10.30").json()["points"][0]
    r = point(lab.tech, aid, "AS_FOUND", "10.01", supersedes_id=first["id"])
    assert r.json()["error"]["code"] == "reason_required"
    r = point(lab.tech, aid, "AS_FOUND", "10.01", supersedes_id=first["id"], correction_reason="Typo in reading")
    pts = r.json()["points"]
    assert len(pts) == 2 and {p["superseded"] for p in pts} == {True, False}
    assert next(p for p in pts if p["superseded"])["measured"] == "10.3"  # original value kept
    with pytest.raises(Exception, match="immutable"):
        with db.begin_nested():
            db.execute(text("UPDATE calibration_points SET measured = 1 WHERE id = :i"), {"i": first["id"]})
    with pytest.raises(Exception, match="immutable"):
        with db.begin_nested():
            db.execute(text("DELETE FROM calibration_points WHERE id = :i"), {"i": first["id"]})


def test_failed_calibration_puts_gage_out_of_service(lab):
    aid = to_in_progress(lab, plan(lab))["id"]
    capture_internal(lab, aid, as_found="10.50")
    lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    done = approve_and_release(lab, aid)
    assert done["result"] == "FAIL"
    gage = lab.get(f"/api/v1/gages/{lab.gage['id']}").json()
    assert gage["status"] == "OUT_OF_SERVICE" and not gage["available_for_use"]


def test_external_calibration_requires_certificate_and_provider(lab):
    aid = plan(lab, "EXTERNAL_CALIBRATION")["id"]
    lab.post(f"/api/v1/calibrations/{aid}/request", json={})
    r = lab.post(f"/api/v1/calibrations/{aid}/schedule", json={"scheduled_date": _iso(0)})
    assert r.json()["error"]["code"] == "provider_required"
    r = lab.post(f"/api/v1/calibrations/{aid}/schedule", json={"scheduled_date": _iso(0),
                                                             "provider_name": "Accredited Lab SA"})
    assert r.status_code == 200
    assert lab.post(f"/api/v1/calibrations/{aid}/start").status_code == 200
    lab.patch(f"/api/v1/calibrations/{aid}", json={"performed_date": _iso(-1), "declared_result": "PASS"})
    r = lab.post(f"/api/v1/calibrations/{aid}/submit", json={})
    assert r.json()["error"]["code"] == "incomplete_activity" and "certificate" in r.json()["error"]["details"]
    r = lab.post(f"/api/v1/calibrations/{aid}/certificates",
                 data={"certificate_number": "EXT-77", "issuer": "Accredited Lab SA", "issue_date": _iso(-1)},
                 files={"file": ("cert.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    assert lab.post(f"/api/v1/calibrations/{aid}/submit", json={}).status_code == 200
    done = approve_and_release(lab, aid)
    assert done["result"] == "PASS"
    summary = lab.get(f"/api/v1/gages/{lab.gage['id']}/calibration-summary").json()
    assert summary["certificates"][0]["certificate_number"] == "EXT-77"


def test_verification_does_not_move_calibration_due_date(lab, new_gage):
    g = new_gage(lab, lab.type_id, "VER-1", last_calibration_date=_iso(-100))
    aid = to_in_progress(lab, plan(lab, "ROUTINE_VERIFICATION", gage=g))["id"]
    assert lab.get(f"/api/v1/gages/{g['id']}").json()["status"] == "CALIBRATED"  # verification does not hold it
    capture_internal(lab, aid)
    lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    done = approve_and_release(lab, aid)
    assert done["due_date"] is None
    gage = lab.get(f"/api/v1/gages/{g['id']}").json()
    assert gage["last_calibration_date"] == _iso(-100) and gage["last_verification_date"] == _iso(0)


# ---------------------------------------------------------------- rules


def test_unauthorized_technician_cannot_be_assigned_or_execute(lab, add_user):
    rookie = add_user(lab, "metrology_technician")
    act = plan(lab)
    lab.post(f"/api/v1/calibrations/{act['id']}/request", json={})
    r = lab.post(f"/api/v1/calibrations/{act['id']}/schedule",
                 json={"scheduled_date": _iso(0), "technician_id": rookie.user_id})
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_authorized"
    lab.post(f"/api/v1/calibrations/{act['id']}/schedule", json={"scheduled_date": _iso(0),
                                                                 "technician_id": lab.tech.user_id})
    r = rookie.post(f"/api/v1/calibrations/{act['id']}/start")
    assert r.json()["error"]["code"] == "not_assigned_technician"


def test_segregation_of_duties_and_reviewer_authorization(lab, authorize):
    aid = to_in_progress(lab, plan(lab))["id"]
    capture_internal(lab, aid)
    lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    # Admin has the permission but no TECHNICAL_REVIEW authorization.
    r = lab.post(f"/api/v1/calibrations/{aid}/review", json={"accept": True})
    assert r.json()["error"]["code"] == "not_authorized"
    lab.reviewer.post(f"/api/v1/calibrations/{aid}/review", json={"accept": True})
    authorize(lab, lab.reviewer.user_id, "APPROVAL")
    r = lab.reviewer.post(f"/api/v1/calibrations/{aid}/approve", json={"accept": True})
    assert r.json()["error"]["code"] == "segregation_of_duties"
    # Technician cannot approve (no permission) even if authorized.
    assert lab.tech.post(f"/api/v1/calibrations/{aid}/approve", json={"accept": True}).status_code == 403


def test_review_can_return_and_release_requires_approval(lab):
    aid = to_in_progress(lab, plan(lab))["id"]
    capture_internal(lab, aid)
    lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    assert lab.post(f"/api/v1/calibrations/{aid}/release", json={}).json()["error"]["code"] == "invalid_activity_status"
    r = lab.reviewer.post(f"/api/v1/calibrations/{aid}/review", json={"accept": False})
    assert r.json()["error"]["code"] == "reason_required"
    r = lab.reviewer.post(f"/api/v1/calibrations/{aid}/review", json={"accept": False, "comments": "Missing photo"})
    assert r.json()["status"] == "IN_PROGRESS"
    assert lab.tech.get("/api/v1/notifications").json()["items"][0]["kind"] == "calibration.returned"
    hist = [h["to_status"] for h in r.json()["history"]]
    assert hist[:2] == ["IN_PROGRESS", "PENDING_REVIEW"]


def test_incomplete_activity_cannot_be_submitted(lab):
    aid = to_in_progress(lab, plan(lab))["id"]
    r = lab.tech.post(f"/api/v1/calibrations/{aid}/submit", json={})
    missing = set(r.json()["error"]["details"])
    assert {"performed_date", "method", "as_found_points", "standard", "environment_temperature"} <= missing


def test_expired_standard_needs_authorized_exception(lab):
    exp = lab.post("/api/v1/standards", json={"standard_code": "OLD-1", "description": "Expired master",
                                              "category": "SETTING_MASTER", "plant_id": lab.plant_id,
                                              "calibration_frequency_days": 30}).json()
    lab.post(f"/api/v1/standards/{exp['id']}/certificates",
             data={"certificate_number": "O-1", "issuer": "Lab", "calibration_date": _iso(-100),
                   "issue_date": _iso(-100), "valid_until": _iso(-5)}, files={"file": ("c.pdf", PDF, "application/pdf")})
    aid = to_in_progress(lab, plan(lab))["id"]
    r = lab.tech.post(f"/api/v1/calibrations/{aid}/standards", json={"standard_id": exp["id"]})
    assert r.json()["error"]["code"] == "standard_not_usable"
    r = lab.tech.post(f"/api/v1/calibrations/{aid}/standards",
                      json={"standard_id": exp["id"], "exception_reason": "Only master available"})
    assert r.status_code == 403  # technician lacks standards:exception
    r = lab.reviewer.post(f"/api/v1/calibrations/{aid}/standards",
                          json={"standard_id": exp["id"], "exception_reason": "Only master available, risk assessed"})
    assert r.status_code == 201
    used = r.json()["standards"][0]
    assert used["is_exception"] and used["standard_status"] == "EXPIRED"


def test_disabled_activity_type_and_one_open_calibration(lab):
    r = lab.put("/api/v1/calibration-settings", json={
        "activity_type": "INTERNAL_CALIBRATION", "enabled": False, "require_certificate": False,
        "require_standard": True, "require_as_found": True, "require_environment": True})
    assert r.status_code == 200 and r.json()["INTERNAL_CALIBRATION"]["source"] == "organization"
    r = lab.post("/api/v1/calibrations", json={"gage_id": lab.gage["id"], "activity_type": "INTERNAL_CALIBRATION",
                                               "planned_date": _iso(0)})
    assert r.json()["error"]["code"] == "activity_type_disabled"
    plan(lab, "EXTERNAL_CALIBRATION")
    r = lab.post("/api/v1/calibrations", json={"gage_id": lab.gage["id"], "activity_type": "EXTERNAL_CALIBRATION",
                                               "planned_date": _iso(0)})
    assert r.json()["error"]["code"] == "open_calibration_exists"


def test_gage_held_by_calibration_cannot_be_released_manually_and_cancel_restores(lab):
    aid = to_in_progress(lab, plan(lab))["id"]
    r = lab.post(f"/api/v1/gages/{lab.gage['id']}/transitions", json={"target": "ACTIVE", "reason": "shortcut"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "calibration_in_progress"
    r = lab.post(f"/api/v1/calibrations/{aid}/cancel", json={"reason": "Gage lost"})
    assert r.json()["status"] == "CANCELLED"
    assert lab.get(f"/api/v1/gages/{lab.gage['id']}").json()["control_status"] == "ACTIVE"


def test_approved_certificate_is_never_replaced_silently(lab):
    act = plan(lab, "EXTERNAL_CALIBRATION")
    lab.post(f"/api/v1/calibrations/{act['id']}/request", json={})
    lab.post(f"/api/v1/calibrations/{act['id']}/schedule", json={"scheduled_date": _iso(0), "provider_name": "Lab"})
    aid = act["id"]
    lab.post(f"/api/v1/calibrations/{aid}/start")
    lab.patch(f"/api/v1/calibrations/{aid}", json={"performed_date": _iso(0), "declared_result": "PASS"})
    cert = {"certificate_number": "A-1", "issuer": "Lab", "issue_date": _iso(0)}
    lab.post(f"/api/v1/calibrations/{aid}/certificates", data=cert, files={"file": ("a.pdf", PDF, "application/pdf")})
    lab.post(f"/api/v1/calibrations/{aid}/submit", json={})
    approve_and_release(lab, aid)
    r = lab.post(f"/api/v1/calibrations/{aid}/certificates", data=cert | {"certificate_number": "A-2"},
                 files={"file": ("b.pdf", PDF, "application/pdf")})
    assert r.json()["error"]["code"] == "reason_required"
    r = lab.post(f"/api/v1/calibrations/{aid}/certificates",
                 data=cert | {"certificate_number": "A-2", "replace_reason": "Lab reissued with corrected serial"},
                 files={"file": ("b.pdf", PDF, "application/pdf")})
    certs = r.json()["certificates"]
    assert [(c["certificate_number"], c["status"]) for c in certs] == [("A-2", "CURRENT"), ("A-1", "SUPERSEDED")]
    assert lab.tech.post(f"/api/v1/calibrations/{aid}/certificates", data=cert | {"replace_reason": "x"},
                         files={"file": ("c.pdf", PDF, "application/pdf")}).status_code == 403


def test_calendar_overview_and_isolation(lab, make_org):
    act = plan(lab)
    events = lab.get(f"/api/v1/calibrations/calendar?start={_iso(-1)}&end={_iso(60)}").json()
    assert lab.get(f"/api/v1/calibrations/calendar?start={_iso(0)}&end={_iso(400)}").json()["error"]["code"] == "range_too_large"
    assert any(e["kind"] == "activity" and e["code"] == act["calibration_code"] for e in events)
    ov = lab.get("/api/v1/calibrations/overview").json()
    assert ov["gages_overdue"] == 1 and ov["pending"] == 1
    assert ov["unplanned_due"] == []  # the overdue gage already has a planned activity
    other = make_org("Other")
    assert other.get(f"/api/v1/calibrations/{act['id']}").status_code == 404
    assert other.get("/api/v1/calibrations").json()["total"] == 0
    assert other.post(f"/api/v1/calibrations/{act['id']}/cancel", json={"reason": "steal"}).status_code == 404
    assert other.post("/api/v1/calibrations", json={"gage_id": lab.gage["id"], "activity_type": "INTERNAL_CALIBRATION",
                                                    "planned_date": _iso(0)}).status_code == 404


def test_viewer_cannot_operate_calibrations(lab, add_user):
    viewer = add_user(lab, "viewer")
    act = plan(lab)
    assert viewer.get(f"/api/v1/calibrations/{act['id']}").status_code == 200
    assert viewer.post(f"/api/v1/calibrations/{act['id']}/request", json={}).status_code == 403
    assert viewer.post("/api/v1/calibrations", json={"gage_id": lab.gage["id"], "activity_type": "INTERNAL_CALIBRATION",
                                                     "planned_date": _iso(0)}).status_code == 403
