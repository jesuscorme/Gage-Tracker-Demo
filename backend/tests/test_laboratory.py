"""Laboratory Operations: requests, scheduling, work orders, dimensional inspection, reports, KPIs."""

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import today


def _iso(days=0):
    return (today() + timedelta(days=days)).isoformat()


def _at(days, hour):
    return datetime.combine(today() + timedelta(days=days), time(hour), tzinfo=UTC).isoformat()


@pytest.fixture()
def lab(make_org, gage_type, add_user, new_gage, authorize):
    admin = make_org("Lab")
    admin.type_id = gage_type(admin, "CAL", 365)["id"]
    admin.manager = add_user(admin, "metrology_manager")
    admin.tech = add_user(admin, "lab_technician")
    admin.requester = add_user(admin, "requester")
    authorize(admin, admin.tech.user_id, "LAB_SERVICE")
    authorize(admin, admin.tech.user_id, "DIMENSIONAL_INSPECTION")
    authorize(admin, admin.manager.user_id, "TECHNICAL_REVIEW")
    admin.service = admin.manager.post("/api/v1/lab/services", json={
        "code": "DIM", "name": "Dimensional inspection", "standard_hours": "2"}).json()
    admin.gage = new_gage(admin, admin.type_id, "CAL-L1", last_calibration_date=_iso(-10))
    return admin


def new_request(lab, actor=None, **extra):
    r = (actor or lab.requester).post("/api/v1/lab/requests", json={
        "plant_id": lab.plant_id, "service_id": lab.service["id"], "part_number": "PN-4471", "part_revision": "C",
        "description": "First article inspection", "priority": "HIGH", "requested_date": _iso(3)} | extra)
    assert r.status_code == 201, r.text
    return r.json()


def approved_wo(lab):
    req = new_request(lab)
    r = lab.manager.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": True, "committed_date": _iso(5)})
    assert r.status_code == 200, r.text
    r = lab.manager.post("/api/v1/lab/work-orders", json={"service_request_id": req["id"]})
    assert r.status_code == 201, r.text
    return r.json()


def schedule(lab, wo, day=1, start=9, end=11, gages=None, tech=None, **extra):
    return lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/schedule", json={
        "technician_id": tech or lab.tech.user_id, "scheduled_start": _at(day, start), "scheduled_end": _at(day, end),
        "gage_ids": gages if gages is not None else [lab.gage["id"]]} | extra)


def result(lab, actor, wo, measured, **extra):
    return actor.post(f"/api/v1/lab/work-orders/{wo['id']}/results", json={
        "part_number": "PN-4471", "drawing_revision": "C", "sample_id": "1", "characteristic_number": "1",
        "characteristic": "Hole diameter", "nominal": "10", "lower_limit": "9.95", "upper_limit": "10.05",
        "measured": measured, "unit": "mm", "gage_id": lab.gage["id"]} | extra)


def test_request_lifecycle_and_requester_visibility(lab, add_user):
    req = new_request(lab)
    assert req["request_code"].startswith(f"SR-{today().year}-") and req["status"] == "SUBMITTED"
    assert lab.manager.get("/api/v1/notifications").json()["items"][0]["kind"] == "lab.request_submitted"
    other_requester = add_user(lab, "requester")
    assert other_requester.get("/api/v1/lab/requests").json() == []
    assert other_requester.get(f"/api/v1/lab/requests/{req['id']}").status_code == 404
    assert lab.requester.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": True}).status_code == 403
    r = lab.manager.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": False})
    assert r.json()["error"]["code"] == "reason_required"
    r = lab.manager.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": True})
    assert r.json()["error"]["code"] == "committed_date_required"
    r = lab.manager.post(f"/api/v1/lab/requests/{req['id']}/decision", json={"approve": True, "committed_date": _iso(5)})
    assert r.json()["status"] == "APPROVED"
    assert lab.requester.get("/api/v1/notifications").json()["items"][0]["kind"] == "lab.request_decided"


def test_work_order_needs_approved_request(lab):
    req = new_request(lab)
    r = lab.manager.post("/api/v1/lab/work-orders", json={"service_request_id": req["id"]})
    assert r.json()["error"]["code"] == "invalid_request_status"
    wo = approved_wo(lab)
    assert wo["work_order_code"].startswith("WO-") and wo["status"] == "PENDING" and wo["planned_hours"] == "2"
    r = lab.manager.post("/api/v1/lab/work-orders", json={"service_request_id": wo["service_request_id"]})
    assert r.json()["error"]["code"] == "work_order_exists"


def test_scheduling_rejects_incompatible_assignments(lab, add_user, new_gage):
    wo = approved_wo(lab)
    rookie = add_user(lab, "lab_technician")
    assert schedule(lab, wo, tech=rookie.user_id).json()["error"]["code"] == "not_authorized"
    overdue = new_gage(lab, lab.type_id, "OLD-1")
    assert schedule(lab, wo, gages=[overdue["id"]]).json()["error"]["code"] == "equipment_unavailable"
    expiring = new_gage(lab, lab.type_id, "EXP-1", last_calibration_date=_iso(-364))  # due tomorrow... until today+1
    r = schedule(lab, wo, day=3, gages=[expiring["id"]])
    assert r.json()["error"]["code"] == "equipment_expires"
    lab.manager.post("/api/v1/lab/absences", json={"user_id": lab.tech.user_id, "start_date": _iso(2),
                                                    "end_date": _iso(2), "reason": "Training"})
    assert schedule(lab, wo, day=2).json()["error"]["code"] == "technician_absent"

    r = schedule(lab, wo)
    assert r.status_code == 200 and r.json()["status"] == "SCHEDULED" and r.json()["equipment"][0]["gage_code"] == "CAL-L1"
    assert lab.tech.get("/api/v1/notifications").json()["items"][0]["kind"] == "lab.work_order_assigned"

    wo2 = approved_wo(lab)
    assert schedule(lab, wo2, start=10, end=12, gages=[]).json()["error"]["code"] == "technician_busy"
    tech2 = add_user(lab, "lab_technician")
    lab.post("/api/v1/competency/authorizations", json={"user_id": tech2.user_id, "activity": "LAB_SERVICE",
                                                         "valid_from": _iso(0)})
    r = schedule(lab, wo2, start=10, end=12, tech=tech2.user_id)
    assert r.json()["error"]["code"] == "equipment_busy"
    assert schedule(lab, wo2, start=11, end=13, tech=tech2.user_id).status_code == 200  # back-to-back is fine
    # Rescheduling needs a reason.
    assert schedule(lab, wo, day=1, start=7, end=9).json()["error"]["code"] == "reason_required"
    assert schedule(lab, wo, day=1, start=7, end=9, reason="Customer moved delivery").status_code == 200


def test_execution_capture_correction_completion_and_report(lab, db):
    wo = approved_wo(lab)
    schedule(lab, wo)
    assert lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/start").json()["error"]["code"] == "not_assigned_technician"
    r = lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/start")
    assert r.json()["status"] == "IN_PROGRESS" and r.json()["request"]["status"] == "IN_PROGRESS"
    assert lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/complete", json={}).json()["error"]["code"] == "results_required"

    first = result(lab, lab.tech, wo, "10.09").json()["results"][0]
    assert first["result"] == "NOK" and first["gage_status"] == "CALIBRATED"
    r = result(lab, lab.tech, wo, "10.01", supersedes_id=first["id"], correction_reason="Re-measured after cleaning")
    results = r.json()["results"]
    assert len(results) == 2 and next(x for x in results if not x["superseded"])["result"] == "OK"
    result(lab, lab.tech, wo, "25.02", characteristic_number="2", characteristic="Length", nominal="25",
           lower_limit="24.9", upper_limit="25.1")
    with pytest.raises(Exception, match="immutable"):
        with db.begin_nested():
            db.execute(text("UPDATE inspection_results SET measured = 10 WHERE id = :i"), {"i": first["id"]})

    r = lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/complete", json={"observations": "Parts returned"})
    assert r.json()["status"] == "COMPLETED"
    # The technician cannot issue their own report (no permission, and no self-review).
    assert lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/reports", json={}).status_code == 403
    r = lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/reports", json={"observations": "All OK"})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["acceptance"] == "ACCEPTED" and rep["revision"] == 0 and len(rep["snapshot"]["results"]) == 2
    pdf = lab.manager.get(f"/api/v1/attachments/{rep['attachment_id']}/download")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    req = lab.requester.get(f"/api/v1/lab/requests/{wo['service_request_id']}").json()
    assert req["status"] == "COMPLETED"
    assert lab.requester.get(f"/api/v1/lab/reports/{rep['id']}").status_code == 200  # requester sees own report
    assert lab.requester.get("/api/v1/notifications").json()["items"][0]["kind"] == "lab.report_issued"

    # Re-issue creates a new revision and keeps the previous one.
    r = lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/reports", json={})
    assert r.json()["error"]["code"] == "reason_required"
    r = lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/reports", json={"revision_reason": "Customer name fix"})
    assert r.json()["revision"] == 1 and r.json()["report_code"] == rep["report_code"]
    all_reports = lab.get("/api/v1/lab/reports?include_superseded=true").json()
    assert [(x["revision"], x["status"]) for x in all_reports] == [(1, "ISSUED"), (0, "SUPERSEDED")]
    att = lab.post(f"/api/v1/attachments/{rep['attachment_id']}/remove", json={"reason": "try"})
    assert att.json()["error"]["code"] == "document_locked"


def test_measurement_with_unavailable_gage_is_refused(lab):
    wo = approved_wo(lab)
    schedule(lab, wo)
    lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/start")
    lab.post(f"/api/v1/gages/{lab.gage['id']}/transitions", json={"target": "OUT_OF_SERVICE", "reason": "Dropped"})
    r = result(lab, lab.tech, wo, "10.00")
    assert r.status_code == 422 and r.json()["error"]["code"] == "equipment_unavailable"


def test_rejected_report_and_dashboard_kpis(lab):
    wo = approved_wo(lab)
    schedule(lab, wo)
    lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/start")
    result(lab, lab.tech, wo, "11")
    lab.tech.post(f"/api/v1/lab/work-orders/{wo['id']}/complete", json={})
    assert lab.manager.post(f"/api/v1/lab/work-orders/{wo['id']}/reports", json={}).json()["acceptance"] == "REJECTED"
    new_request(lab)
    approved_wo(lab)
    k = lab.get("/api/v1/lab/dashboard").json()
    assert k["pending_requests"] == 1 and k["open_work_orders"] == 1
    assert k["work_orders"]["COMPLETED"] == 1 and k["completed_last_30_days"] == 1
    assert k["avg_response_hours_90_days"] is not None and k["on_time_rate_30_days"] == 100.0
    assert k["capacity"]["technicians"] >= 1


def test_laboratory_isolation_between_organizations(lab, make_org):
    wo = approved_wo(lab)
    other = make_org("Other")
    assert other.get(f"/api/v1/lab/work-orders/{wo['id']}").status_code == 404
    assert other.get(f"/api/v1/lab/requests/{wo['service_request_id']}").status_code == 404
    assert other.get("/api/v1/lab/work-orders").json() == []
    assert other.post(f"/api/v1/lab/work-orders/{wo['id']}/cancel", json={"reason": "x y z"}).status_code == 404
    r = other.post("/api/v1/lab/requests", json={"plant_id": lab.plant_id, "service_id": lab.service["id"],
                                                 "description": "steal", "requested_date": _iso(1)})
    assert r.status_code == 404
