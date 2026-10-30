"""Report center: every report in every format, reconciliation with the dashboard, permissions, tenant scope."""

import csv
import io

import pytest
from openpyxl import load_workbook

from app.modules.reports.definitions import REPORTS
from tests.test_calibration import lab  # noqa: F401
from tests.test_msa import create, msa  # noqa: F401
from tests.msa_reference import grr_observations
from tests.test_oot import detect, oot_lab  # noqa: F401


@pytest.fixture()
def data(oot_lab):  # noqa: F811
    _cal, case = detect(oot_lab)
    oot_lab.post(f"/api/v1/workflows/oot_case/{case['id']}/transitions", json={"transition": "INVESTIGATE"})
    oot_lab.post(f"/api/v1/oot/cases/{case['id']}/analysis")
    oot_lab.post(f"/api/v1/oot/cases/{case['id']}/actions", json={"action_type": "CONTAINMENT", "description": "Hold",
                                                                    "owner_id": oot_lab.tech.user_id})
    oot_lab.case = case
    return oot_lab


def test_every_report_renders_in_every_format(data):
    lab = data
    for key, rep in REPORTS.items():
        q = f"?gage_id={lab.gage['id']}" if rep.needs_gage else ""
        j = lab.get(f"/api/v1/reports/{key}{q}")
        assert j.status_code == 200, (key, j.text)
        body = j.json()
        assert body["code"].startswith("RPT-") and body["count"] == len(body["rows"])
        for fmt, magic in (("pdf", b"%PDF"), ("xlsx", b"PK"), ("csv", "﻿".encode())):
            r = lab.get(f"/api/v1/reports/{key}{q}{'&' if q else '?'}format={fmt}&lang=en")
            assert r.status_code == 200 and r.content.startswith(magic), (key, fmt)
    expected = {"gage_inventory", "calibrations_performed", "as_found_as_left", "lab_inspections", "oot_cases",
                "oot_impact", "oot_actions", "gage_history", "standards_history", "lab_work_orders"}
    nonempty = {k for k in REPORTS if lab.get(f"/api/v1/reports/{k}"
                                              + (f"?gage_id={lab.gage['id']}" if REPORTS[k].needs_gage else ""))
                .json()["count"] > 0}
    assert expected <= nonempty


def test_reports_reconcile_with_dashboard_and_sources(data):
    lab = data
    d = lab.get("/api/v1/dashboard/overview").json()
    assert lab.get("/api/v1/reports/gage_inventory").json()["count"] == d["gages"]["total"]
    perf = lab.get("/api/v1/reports/calibrations_performed").json()
    assert perf["count"] == d["calibration"]["released_in_period"] == 2
    assert lab.get("/api/v1/reports/oot_cases?status=OPEN").json()["count"] == d["oot"]["open"] == 1
    wo = lab.get("/api/v1/reports/lab_work_orders").json()
    assert sum(1 for r in wo["rows"] if r["status"] in ("PENDING", "SCHEDULED", "IN_PROGRESS")) == \
        d["laboratory"]["work_orders_open"]
    oos = lab.get("/api/v1/reports/gage_inventory?status=OUT_OF_SERVICE").json()
    assert oos["count"] == d["gages"]["out_of_service"] == 1
    # As Found / As Left rows come from the released calibrations only.
    afl = lab.get("/api/v1/reports/as_found_as_left").json()["rows"]
    assert {r["phase"] for r in afl} == {"AS_FOUND", "AS_LEFT"} and any(r["in_tolerance"] is False for r in afl)
    # Spreadsheet and CSV carry the same rows as the JSON view.
    x = load_workbook(io.BytesIO(lab.get("/api/v1/reports/calibrations_performed?format=xlsx").content))
    ws = x.active
    assert ws["A1"].value == "Calibraciones realizadas" and ws.cell(row=7, column=2).value == 2
    rows = list(csv.reader(io.StringIO(lab.get("/api/v1/reports/calibrations_performed?format=csv").text.lstrip("﻿"))))
    assert len(rows) == 1 + perf["count"] and rows[0][0] == "Actividad"
    events = lab.get("/api/v1/audit-events?action=report.generated").json()["items"]
    assert len(events) == 2 and {e["changes"]["format"] for e in events} == {"xlsx", "csv"}


def test_report_permissions_and_tenant_scope(data, add_user, make_org):
    lab = data
    requester = add_user(lab, "requester")
    keys = {r["key"] for r in requester.get("/api/v1/reports").json()}
    assert "lab_requests" in keys and "calibrations_performed" not in keys and "oot_cases" not in keys
    assert requester.get("/api/v1/reports/calibrations_performed").status_code == 403
    assert requester.get("/api/v1/reports/oot_cases?format=pdf").status_code == 403
    other = make_org("Other")
    assert other.get("/api/v1/reports/gage_inventory").json()["count"] == 0
    assert other.get(f"/api/v1/reports/gage_history?gage_id={lab.gage['id']}").status_code == 404
    assert other.get(f"/api/v1/reports/gage_inventory?plant_id={lab.plant_id}").status_code == 404
    assert lab.get("/api/v1/reports/gage_history").json()["error"]["code"] == "gage_required"
    assert lab.get("/api/v1/reports/nope").status_code == 404


def test_msa_report_lists_method_version_and_decision(msa):  # noqa: F811
    s = create(msa, design={"operators": 3, "parts": 10, "trials": 3})
    msa.post(f"/api/v1/msa/studies/{s['id']}/observations", json={"observations": grr_observations()})
    msa.post(f"/api/v1/msa/studies/{s['id']}/calculate")
    row = msa.get("/api/v1/reports/msa_studies").json()["rows"][0]
    assert row["method"] == "GRR_CROSSED_AR" and row["algorithm_version"] == "1.0.0"
    assert row["computed_decision"] == "NO_CRITERIA" and row["run_number"] == 1
