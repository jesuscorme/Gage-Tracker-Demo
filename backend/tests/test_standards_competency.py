"""Standards Management and Competency Management."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.conftest import PDF, today


@pytest.fixture()
def org(make_org, add_user):
    admin = make_org("Standards")
    admin.manager = add_user(admin, "metrology_manager")
    admin.tech = add_user(admin, "metrology_technician")
    return admin


def _iso(days):
    return (today() + timedelta(days=days)).isoformat()


def new_standard(actor, code="GB-01", category="GAUGE_BLOCK", **extra):
    r = actor.post("/api/v1/standards", json={"standard_code": code, "description": "Gauge block set grade 0",
                                              "category": category, "plant_id": actor.plant_id,
                                              "calibration_frequency_days": 365} | extra)
    assert r.status_code == 201, r.text
    return r.json()


def add_cert(actor, sid, cal_days_ago=10, valid_days=None, number="C-1"):
    data = {"certificate_number": number, "issuer": "CENAM", "calibration_date": _iso(-cal_days_ago),
            "issue_date": _iso(-cal_days_ago), "traceability": "SI via CENAM"}
    if valid_days is not None:
        data["valid_until"] = _iso(valid_days)
    return actor.post(f"/api/v1/standards/{sid}/certificates", data=data,
                      files={"file": ("cert.pdf", PDF, "application/pdf")})


def test_standard_lifecycle_and_status(org):
    s = new_standard(org.manager)
    assert s["status"] == "NO_CERTIFICATE" and s["usable"] is False
    assert org.tech.post("/api/v1/standards", json={}).status_code == 403
    r = add_cert(org.manager, s["id"])
    assert r.status_code == 201 and r.json()["status"] == "CURRENT"
    s = org.get(f"/api/v1/standards/{s['id']}").json()
    assert s["status"] == "VALID" and s["valid_until"] == _iso(-10 + 365)

    # A new certificate supersedes; the old one is kept.
    add_cert(org.manager, s["id"], cal_days_ago=2, valid_days=20, number="C-2")
    certs = org.get(f"/api/v1/standards/{s['id']}/certificates").json()
    assert [(c["certificate_number"], c["status"]) for c in certs] == [("C-2", "CURRENT"), ("C-1", "SUPERSEDED")]
    assert org.get(f"/api/v1/standards/{s['id']}").json()["status"] == "DUE_SOON"

    r = org.manager.post(f"/api/v1/standards/{s['id']}/transitions", json={"target": "RESTRICTED", "reason": "Dropped"})
    assert r.json()["status"] == "RESTRICTED" and not r.json()["usable"]


def test_certificate_must_be_pdf_and_consistent(org):
    s = new_standard(org)
    r = org.post(f"/api/v1/standards/{s['id']}/certificates",
                 data={"certificate_number": "X", "issuer": "Lab", "calibration_date": _iso(-1), "issue_date": _iso(-1)},
                 files={"file": ("c.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")})
    assert r.json()["error"]["code"] == "pdf_required"
    assert add_cert(org, s["id"], cal_days_ago=-3).json()["error"]["code"] == "future_date"
    add_cert(org, s["id"], cal_days_ago=5)
    assert add_cert(org, s["id"], cal_days_ago=30, number="OLD").json()["error"]["code"] == "certificate_regression"
    # Certificate PDFs are locked: they cannot be withdrawn.
    att_id = org.get(f"/api/v1/standards/{s['id']}/certificates").json()[0]["attachment_id"]
    r = org.post(f"/api/v1/attachments/{att_id}/remove", json={"reason": "try"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "document_locked"


def test_standard_code_unique_and_isolated(org, make_org):
    s = new_standard(org)
    assert org.post("/api/v1/standards", json={"standard_code": "gb-01", "description": "Dup", "category": "OTHER",
                                               "plant_id": org.plant_id,
                                               "calibration_frequency_days": 30}).status_code == 409
    other = make_org("Other")
    assert other.get(f"/api/v1/standards/{s['id']}").status_code == 404
    assert other.get("/api/v1/standards").json() == []


def test_competency_records_matrix_and_authorizations(org, db):
    comp = org.post("/api/v1/competency/competencies", json={"code": "CAL-CALIPER", "name": "Caliper calibration",
                                                             "validity_months": 12}).json()
    org.manager.put(f"/api/v1/competency/people/{org.tech.user_id}",
                    json={"job_title": "Metrology technician", "profile_types": ["INTERNAL_CALIBRATOR", "VERIFIER"]})
    rec = org.manager.post("/api/v1/competency/records", json={
        "user_id": org.tech.user_id, "competency_id": comp["id"], "record_type": "EVALUATION",
        "title": "Practical evaluation", "completed_on": _iso(-5), "result": "PASSED"}).json()
    assert rec["valid_until"] is not None  # derived from the competency validity
    matrix = org.get("/api/v1/competency/matrix").json()
    row = next(r for r in matrix["rows"] if r["user_id"] == org.tech.user_id)
    assert row["cells"][comp["id"]] == "CURRENT"

    # Authorization: granted by an authorized user, never edited, revocable with reason.
    assert org.tech.post("/api/v1/competency/authorizations", json={
        "user_id": org.tech.user_id, "activity": "INTERNAL_CALIBRATION", "valid_from": _iso(0)}).status_code == 403
    auth = org.manager.post("/api/v1/competency/authorizations", json={
        "user_id": org.tech.user_id, "activity": "INTERNAL_CALIBRATION", "valid_from": _iso(0),
        "valid_until": _iso(365), "competency_record_id": rec["id"], "basis": "Evaluation passed"}).json()
    assert auth["state"] == "CURRENT"
    people = org.get("/api/v1/competency/people").json()
    assert "INTERNAL_CALIBRATION" in next(p for p in people if p["user_id"] == org.tech.user_id)["current_authorizations"]
    users = org.get("/api/v1/competency/authorized-users?activity=INTERNAL_CALIBRATION").json()
    assert [u["id"] for u in users] == [org.tech.user_id]

    r = org.manager.post(f"/api/v1/competency/authorizations/{auth['id']}/revoke", json={"reason": "Left the lab"})
    assert r.json()["state"] == "REVOKED"
    assert org.get("/api/v1/competency/authorized-users?activity=INTERNAL_CALIBRATION").json() == []
    with pytest.raises(Exception, match="append-only"):
        with db.begin_nested():
            db.execute(text("UPDATE competency_records SET result = 'FAILED' WHERE id = :i"), {"i": rec["id"]})


def test_authorization_scope_by_gage_type(org, gage_type, authorize):
    cal = gage_type(org, "CAL")["id"]
    mic = gage_type(org, "MIC")["id"]
    authorize(org, org.tech.user_id, "INTERNAL_CALIBRATION", gage_type_id=cal)
    assert org.get(f"/api/v1/competency/authorized-users?activity=INTERNAL_CALIBRATION&gage_type_id={cal}").json()
    assert not org.get(f"/api/v1/competency/authorized-users?activity=INTERNAL_CALIBRATION&gage_type_id={mic}").json()
    r = org.post("/api/v1/competency/authorizations", json={
        "user_id": org.tech.user_id, "activity": "APPROVAL", "valid_from": _iso(-30), "valid_until": _iso(-1)})
    assert r.json()["error"]["code"] == "invalid_dates"
