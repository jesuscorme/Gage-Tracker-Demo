"""Compliance & Audit: evidence matrix, clause/process queries, dossier, searches, pending report, export."""

import io

from openpyxl import load_workbook

from tests.test_calibration import approve_and_release, capture_internal, lab, plan, to_in_progress  # noqa: F401


def test_matrix_reflects_live_data_and_never_claims_compliance(make_org, gage_type, new_gage, add_user):
    admin = make_org("Comp")
    m = admin.get("/api/v1/compliance/matrix").json()
    assert "does not certify" in m["disclaimer"]
    procs = {p["process"]: p for p in m["processes"]}
    assert procs["MSA"]["state"] == "NO_RECORDS"
    assert {c["clause"] for c in m["clauses"]} >= {"7.1.5.1.1", "7.1.5.2.1", "7.1.5.2", "7.2"}
    new_gage(admin, gage_type(admin, "CAL")["id"], "CRIT-1", criticality="HIGH")
    msa = admin.get("/api/v1/compliance/processes/msa").json()
    assert msa["gaps"]["high_criticality_gages_without_approved_msa"] == 1
    c = admin.get("/api/v1/compliance/clauses/IATF16949/7.1.5.1.1").json()
    assert c["processes"][0]["process"] == "MSA" and "disclaimer" in c
    assert admin.get("/api/v1/compliance/clauses/ISO9001/9.9.9").status_code == 404
    viewer = add_user(admin, "viewer")
    assert viewer.get("/api/v1/compliance/matrix").status_code == 403
    auditor = add_user(admin, "auditor")
    assert auditor.get("/api/v1/compliance/matrix").status_code == 200


def test_dossier_searches_pending_and_export_use_existing_records(lab, make_org):  # noqa: F811
    act = to_in_progress(lab, plan(lab))
    capture_internal(lab, act["id"])
    lab.tech.post(f"/api/v1/calibrations/{act['id']}/submit", json={})
    approve_and_release(lab, act["id"])
    d = lab.get(f"/api/v1/compliance/gages/{lab.gage['id']}/dossier").json()
    cal = d["calibrations"][0]
    assert cal["status"] == "RELEASED" and cal["reviewer"] == "metrology_manager user" and cal["approved_at"]
    assert d["status_history"] and any(a["action"] == "gage.released" for a in d["audit_trail"])
    certs = lab.get("/api/v1/compliance/certificates?q=STD-1").json()
    assert certs[0]["kind"] == "REFERENCE_STANDARD" and certs[0]["subject"] == "GB-01"
    appr = lab.get("/api/v1/compliance/approvals").json()
    assert appr[0]["record"] == act["calibration_code"] and appr[0]["action"] == "APPROVE"
    other_gage = lab.post("/api/v1/gages", json={"gage_code": "OVD-1", "description": "Old caliper",
                                                 "gage_type_id": lab.type_id, "plant_id": lab.plant_id,
                                                 "last_calibration_date": "2020-01-01"}).json()
    pending = lab.get("/api/v1/compliance/pending").json()
    assert "OVD-1" in [g["gage_code"] for g in pending["overdue_gages"]]
    proc = lab.get("/api/v1/compliance/processes/CALIBRATION").json()
    assert proc["evidence"]["released_activities"] == 1 and proc["state"] == "EVIDENCE_AVAILABLE"
    x = lab.get(f"/api/v1/compliance/export.xlsx?gage_id={lab.gage['id']}")
    assert x.status_code == 200 and x.content.startswith(b"PK")
    wb = load_workbook(io.BytesIO(x.content))
    assert {"matrix", "pending", "approvals"} <= set(wb.sheetnames)
    assert "does not certify" in wb["matrix"]["B1"].value
    events = lab.get("/api/v1/audit-events?action=compliance.exported").json()["items"]
    assert len(events) == 1
    other = make_org("Other")
    assert other.get(f"/api/v1/compliance/gages/{lab.gage['id']}/dossier").status_code == 404
    assert other_gage["gage_code"] == "OVD-1"
