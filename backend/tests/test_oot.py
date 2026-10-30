"""OOT & Impact Analysis: detection from calibration, restriction, retrospective analysis, workflow, closure."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.conftest import PDF, today
from tests.test_calibration import approve_and_release, lab, plan, point, to_in_progress  # noqa: F401


def _iso(days=0):
    return (today() + timedelta(days=days)).isoformat()


def calibrate(lab, performed_days, as_found, as_left=None):
    act = to_in_progress(lab, plan(lab))
    aid = act["id"]
    t = lab.tech
    r = t.patch(f"/api/v1/calibrations/{aid}", json={
        "performed_date": _iso(performed_days), "method": "PR-MET-04", "environment_temperature": "20.0",
        "environment_humidity": "45", "adjusted": as_left is not None})
    assert r.status_code == 200, r.text
    assert point(t, aid, "AS_FOUND", as_found).status_code == 201
    if as_left:
        assert point(t, aid, "AS_LEFT", as_left).status_code == 201
    assert t.post(f"/api/v1/calibrations/{aid}/standards", json={"standard_id": lab.std["id"]}).status_code == 201
    r = t.post(f"/api/v1/calibrations/{aid}/submit", json={})
    assert r.status_code == 200, r.text
    return approve_and_release(lab, aid)


@pytest.fixture()
def oot_lab(lab, authorize):  # noqa: F811
    # Authorization valid in the past so the earlier calibration can be dated back.
    r = lab.post("/api/v1/competency/authorizations", json={
        "user_id": lab.tech.user_id, "activity": "INTERNAL_CALIBRATION", "valid_from": _iso(-60)})
    assert r.status_code == 201, r.text
    authorize(lab, lab.tech.user_id, "LAB_SERVICE")
    authorize(lab, lab.tech.user_id, "DIMENSIONAL_INSPECTION")
    lab.first = calibrate(lab, -20, "10.01")                     # last acceptable calibration
    # Laboratory work measured with the gage inside the period that will be affected.
    svc = lab.post("/api/v1/lab/services", json={"code": "DIM", "name": "Dimensional", "standard_hours": "1"}).json()
    req = lab.post("/api/v1/lab/requests", json={
        "plant_id": lab.plant_id, "service_id": svc["id"], "part_number": "PN-77", "description": "Check",
        "priority": "HIGH", "requested_date": _iso(2), "customer_type": "EXTERNAL", "customer_name": "ACME"})
    assert req.status_code == 201, req.text
    req = req.json()
    lab.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": True, "committed_date": _iso(3)})
    wo = lab.post("/api/v1/lab/work-orders", json={"service_request_id": req["id"]}).json()
    r = lab.post(f"/api/v1/lab/work-orders/{wo['id']}/schedule", json={
        "technician_id": lab.tech.user_id, "scheduled_start": f"{_iso(1)}T09:00:00Z",
        "scheduled_end": f"{_iso(1)}T10:00:00Z", "gage_ids": [lab.gage["id"]]})
    assert r.status_code == 200, r.text
    assert lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/start").status_code == 200
    r = lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/results", json={
        "part_number": "PN-77", "characteristic_number": "1", "characteristic": "Bore", "nominal": "10",
        "lower_limit": "9.95", "upper_limit": "10.05", "measured": "10.04", "unit": "mm",
        "gage_id": lab.gage["id"]})
    assert r.status_code == 201, r.text
    lab.wo = wo
    return lab


def detect(oot_lab):
    """Second calibration: As Found out of tolerance, adjusted, As Left OK."""
    cal = calibrate(oot_lab, 0, "10.05", as_left="10.00")
    assert cal["result"] == "PASS_AFTER_ADJUSTMENT" and cal["as_found_in_tolerance"] is False
    cases = oot_lab.get(f"/api/v1/oot/cases?gage_id={oot_lab.gage['id']}").json()
    assert len(cases) == 1
    return cal, cases[0]


def move(actor, case, code, comment=None):
    return actor.post(f"/api/v1/workflows/oot_case/{case['id']}/transitions",
                      json={"transition": code, "comment": comment})


def test_detection_restricts_gage_and_full_closure_workflow(oot_lab, db):
    cal, case = detect(oot_lab)
    lab = oot_lab
    assert case["case_code"].startswith(f"OOT-{today().year}-") and case["detection_source"] == "CALIBRATION"
    assert case["status"] == "RESTRICTED" and case["restriction_applied"] is True
    assert case["gage_prior_control_status"] == "ACTIVE" and case["gage_control_status"] == "OUT_OF_SERVICE"
    assert case["max_deviation"] == "0.03" and case["as_found"][0]["in_tolerance"] is False
    assert case["calibration_id"] == cal["id"]
    gage = lab.get(f"/api/v1/gages/{lab.gage['id']}").json()
    assert gage["status"] == "OUT_OF_SERVICE" and not gage["available_for_use"]
    event = db.execute(text("SELECT payload FROM outbox_events WHERE event_type = 'oot.case_created'")).scalar()
    assert event["data"]["case_code"] == case["case_code"]

    # An ordinary release of the gage is blocked while the case holds it.
    r = lab.post(f"/api/v1/gages/{lab.gage['id']}/transitions", json={"target": "ACTIVE", "reason": "try"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "oot_restriction"

    # Calibration history visible from the case.
    hist = lab.get(f"/api/v1/oot/cases/{case['id']}/calibration-history").json()
    assert [h["is_detection"] for h in hist if h["id"] == cal["id"]] == [True]

    assert move(lab, case, "INVESTIGATE").json()["state"] == "INVESTIGATION"
    case = lab.post(f"/api/v1/oot/cases/{case['id']}/analysis").json()
    assert case["last_acceptable_calibration_id"] == lab.first["id"]
    assert case["impact_start"] == _iso(-20) and case["impact_end"] == _iso(0)
    assert "lot" in case["limitations"]
    items = lab.get(f"/api/v1/oot/cases/{case['id']}/items").json()
    kinds = {i["item_type"] for i in items}
    assert {"INSPECTION_RESULT", "WORK_ORDER"} <= kinds
    insp = next(i for i in items if i["item_type"] == "INSPECTION_RESULT")
    assert insp["data"]["customer"] == "ACME" and insp["data"]["gage_status_at_measurement"] == "CALIBRATED"
    # Regenerating keeps assessments and does not duplicate items.
    lab.post(f"/api/v1/oot/items/{insp['id']}/assess", json={"assessment": "REINSPECT", "note": "Re-measure PN-77"})
    lab.post(f"/api/v1/oot/cases/{case['id']}/analysis")
    again = lab.get(f"/api/v1/oot/cases/{case['id']}/items").json()
    assert len(again) == len(items) and next(i for i in again if i["id"] == insp["id"])["assessment"] == "REINSPECT"
    # Manual record for information the system does not hold (lots).
    r = lab.post(f"/api/v1/oot/cases/{case['id']}/items", json={"ref_code": "LOT-2291",
                                                                 "description": "Lot shipped to ACME"})
    assert r.status_code == 201 and r.json()["source"] == "MANUAL"
    for i in lab.get(f"/api/v1/oot/cases/{case['id']}/items").json():
        if i["assessment"] == "PENDING":
            assert lab.post(f"/api/v1/oot/items/{i['id']}/assess", json={"assessment": "NO_IMPACT"}).status_code == 200
    r = lab.post(f"/api/v1/oot/items/{insp['id']}/assess", json={"assessment": "IMPACT"})
    assert r.json()["error"]["code"] == "comment_required"

    assert move(lab, case, "EVALUATE_IMPACT").json()["state"] == "IMPACT_EVALUATION"
    assert move(lab, case, "PLAN_ACTIONS").json()["error"]["code"] == "risk_required"
    r = lab.patch(f"/api/v1/oot/cases/{case['id']}", json={
        "risk_level": "MEDIUM", "risk_assessment": "Deviation 0.03 mm on a 0.1 mm tolerance band",
        "disposition": "Re-measure retained samples", "customer_notification_required": False})
    assert r.status_code == 200, r.text
    action = lab.post(f"/api/v1/oot/cases/{case['id']}/actions", json={
        "action_type": "REINSPECTION", "description": "Re-measure PN-77 samples", "owner_id": lab.tech.user_id,
        "due_date": _iso(5)}).json()
    assert move(lab, case, "PLAN_ACTIONS").json()["state"] == "ACTIONS"
    assert move(lab, case, "SUBMIT").json()["state"] == "IN_REVIEW"
    # Segregation: whoever submitted cannot review.
    assert move(lab, case, "REVIEW").json()["error"]["code"] == "segregation_of_duties"
    assert move(lab.reviewer, case, "REVIEW").json()["state"] == "PENDING_APPROVAL"
    # The responsible person cannot approve; another approver can.
    # The gage has no responsible, so the case went to the calibration approver.
    assert case["responsible_id"] == lab.approver.user_id
    assert move(lab.approver, case, "APPROVE").json()["error"]["code"] == "segregation_of_duties"
    assert move(lab, case, "APPROVE").json()["state"] == "APPROVED"

    r = move(lab, case, "CLOSE")
    assert r.json()["error"]["code"] == "close_requirements"
    assert set(r.json()["error"]["details"]) == {"actions_completed", "gage_released_or_retired"}
    r = lab.tech.post(f"/api/v1/oot/actions/{action['id']}/finish", json={"note": "All samples within tolerance"})
    assert r.status_code == 200 and r.json()["status"] == "DONE"
    rel = lab.post(f"/api/v1/oot/cases/{case['id']}/release-gage", json={"reason": "As Left within tolerance"})
    assert rel.status_code == 200, rel.text  # noqa
    assert rel.json()["gage_released_at"] and rel.json()["gage_control_status"] == "ACTIVE"
    assert lab.get(f"/api/v1/gages/{lab.gage['id']}").json()["available_for_use"] is True
    done = move(lab, case, "CLOSE").json()
    assert done["state"] == "CLOSED"
    final = lab.get(f"/api/v1/oot/cases/{case['id']}").json()
    assert final["closed_at"] and final["close_gaps"] == []
    wf = lab.get(f"/api/v1/workflows/oot_case/{case['id']}").json()
    assert [e["to_state"] for e in wf["history"] if e["event_type"] == "TRANSITION"] == [
        "RESTRICTED", "INVESTIGATION", "IMPACT_EVALUATION", "ACTIONS", "IN_REVIEW", "PENDING_APPROVAL", "APPROVED",
        "CLOSED"]
    assert move(lab, case, "CANCEL", "x").json()["error"]["code"] == "invalid_transition"


def test_restriction_survives_a_new_calibration_until_released_from_the_case(oot_lab):
    _cal, case = detect(oot_lab)
    # Re-calibrating the gage does not lift the OOT hold.
    calibrate(oot_lab, 0, "10.00")
    gage = oot_lab.get(f"/api/v1/gages/{oot_lab.gage['id']}").json()
    assert gage["control_status"] == "OUT_OF_SERVICE"
    hist = oot_lab.get(f"/api/v1/gages/{oot_lab.gage['id']}/status-history").json()
    assert "restricted by OOT case" in hist[0]["reason"]


def test_manual_case_configurable_restriction_cancel_and_verification(lab, add_user, new_gage):  # noqa: F811
    s = lab.get("/api/v1/oot/settings").json()
    assert s["restrict_on_detection"] is True and s["version"] == 0
    r = lab.put("/api/v1/oot/settings", json={"restrict_on_detection": False, "auto_create_from_calibration": True,
                                              "close_requirements": ["risk_assessment", "evidence_attached"]})
    assert r.json()["version"] == 1
    g = new_gage(lab, lab.type_id, "G-MAN", last_calibration_date=_iso(-5))
    case = lab.post("/api/v1/oot/cases", json={
        "gage_id": g["id"], "detected_on": _iso(0), "description": "Dropped and found out of tolerance on check",
        "responsible_id": lab.reviewer.user_id, "max_deviation": "0.02"}).json()
    assert case["status"] == "DETECTED" and case["restriction_applied"] is False
    assert lab.get(f"/api/v1/gages/{g['id']}").json()["control_status"] == "ACTIVE"
    assert move(lab, case, "RESTRICT").json()["state"] == "RESTRICTED"
    assert lab.get(f"/api/v1/gages/{g['id']}").json()["control_status"] == "OUT_OF_SERVICE"
    # Release requires a calibration with an acceptable As Left after detection.
    move(lab, case, "INVESTIGATE")
    r = lab.post(f"/api/v1/oot/cases/{case['id']}/release-gage", json={"reason": "looks fine"})
    assert r.json()["error"]["code"] == "gage_not_verified"
    # A user without oot:approve cannot release nor cancel.
    tech = lab.tech
    assert tech.post(f"/api/v1/oot/cases/{case['id']}/release-gage", json={"reason": "x" * 5}).status_code == 403
    assert move(tech, case, "CANCEL", "error").status_code == 403
    # Evidence upload on the case, then cancel: the gage returns to its previous status.
    r = lab.post("/api/v1/attachments", data={"entity_type": "oot_case", "entity_id": case["id"],
                                              "category": "EVIDENCE"}, files={"file": ("e.pdf", PDF, "application/pdf")})
    assert r.status_code == 201, r.text
    assert move(lab, case, "CANCEL").json()["error"]["code"] == "comment_required"
    assert move(lab, case, "CANCEL", "Registered against the wrong gage").json()["state"] == "CANCELLED"
    assert lab.get(f"/api/v1/gages/{g['id']}").json()["control_status"] == "ACTIVE"


def test_oot_isolation_and_permissions(oot_lab, make_org, add_user):
    _cal, case = detect(oot_lab)
    other = make_org("Other")
    assert other.get(f"/api/v1/oot/cases/{case['id']}").status_code == 404
    assert other.get(f"/api/v1/workflows/oot_case/{case['id']}").status_code == 404
    viewer = add_user(oot_lab, "viewer")
    assert viewer.get(f"/api/v1/oot/cases/{case['id']}").status_code == 200
    assert viewer.post(f"/api/v1/oot/cases/{case['id']}/analysis").status_code == 403
    assert move(viewer, case, "INVESTIGATE").status_code == 403
    assert viewer.put("/api/v1/oot/settings", json={"restrict_on_detection": True,
                                                    "auto_create_from_calibration": True,
                                                    "close_requirements": []}).status_code == 403


def test_auto_creation_can_be_disabled(oot_lab):
    oot_lab.put("/api/v1/oot/settings", json={"restrict_on_detection": True, "auto_create_from_calibration": False,
                                              "close_requirements": []})
    calibrate(oot_lab, 0, "10.05", as_left="10.00")
    assert oot_lab.get(f"/api/v1/oot/cases?gage_id={oot_lab.gage['id']}").json() == []
