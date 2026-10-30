"""Executive dashboard: figures reconcile with each other and with the source records; filters and scope."""

from sqlalchemy import text

from tests.conftest import today
from tests.test_calibration import lab  # noqa: F401
from tests.test_oot import detect, oot_lab  # noqa: F401


def test_dashboard_reconciles_with_source_records(oot_lab, db, add_user, new_gage):  # noqa: F811
    _cal, case = detect(oot_lab)
    lab = oot_lab
    new_gage(lab, lab.type_id, "EXTRA-1", last_calibration_date=today().isoformat())
    d = lab.get("/api/v1/dashboard/overview").json()
    g = d["gages"]
    org = lab.org_id
    # Partitions of the same population.
    assert sum(g["by_status"].values()) == g["total"]
    assert sum(t["count"] for t in g["by_type"]) == g["total"]
    assert sum(p["active"] for p in g["compliance_by_plant"]) == g["active"]
    assert g["current"] == g["calibrated"] + g["due_soon"]
    # Against the source tables and list endpoints.
    assert g["total"] == lab.get("/api/v1/gages").json()["total"] == db.execute(
        text(f"SELECT count(*) FROM gages WHERE organization_id = '{org}'")).scalar()
    assert g["out_of_service"] == lab.get("/api/v1/gages?status=OUT_OF_SERVICE").json()["total"] == 1
    released = db.execute(text(f"SELECT count(*) FROM calibration_activities WHERE organization_id = '{org}' "
                               "AND status = 'RELEASED'")).scalar()
    assert d["calibration"]["released_in_period"] == released == 2
    assert sum(m["count"] for m in d["calibration"]["released_by_month"]) == released
    assert d["calibration"]["results_in_period"] == {"PASS": 1, "PASS_AFTER_ADJUSTMENT": 1}
    assert d["oot"]["open"] == 1 and d["oot"]["gages_restricted"] == 1
    wo_open = db.execute(text(f"SELECT count(*) FROM work_orders WHERE organization_id = '{org}' "
                              "AND status IN ('PENDING','SCHEDULED','IN_PROGRESS')")).scalar()
    assert d["laboratory"]["work_orders_open"] == wo_open == 1
    assert sum(w["open_orders"] for w in d["laboratory"]["workload"]) == wo_open
    assert d["expirations"]["standards_expiring"] == 0
    # Filters narrow every gage-based section consistently.
    oos = lab.get("/api/v1/dashboard/overview?status=OUT_OF_SERVICE").json()
    assert oos["gages"]["total"] == 1 and oos["oot"]["open"] == 1 and oos["calibration"]["released_in_period"] == 2
    other_type = lab.post("/api/v1/gage-types", json={"code": "CMM", "name": "CMM"}).json()
    empty = lab.get(f"/api/v1/dashboard/overview?gage_type_id={other_type['id']}").json()
    assert empty["gages"]["total"] == 0 and empty["oot"]["open"] == 0
    assert lab.get("/api/v1/dashboard/overview?date_from=2026-05-01&date_to=2025-01-01").status_code == 422


def test_dashboard_respects_permissions_and_plant_scope(lab, add_user, make_org):  # noqa: F811
    p2 = lab.post("/api/v1/plants", json={"code": "P2", "name": "Plant 2"}).json()
    scoped = add_user(lab, "viewer", plant_ids=[lab.plant_id])
    assert scoped.get(f"/api/v1/dashboard/overview?plant_id={p2['id']}").status_code == 404
    requester = add_user(lab, "requester")
    d = requester.get("/api/v1/dashboard/overview").json()
    assert d["calibration"] is None and d["msa"] is None and d["oot"] is None and d["laboratory"] is not None
    other = make_org("Other")
    assert other.get(f"/api/v1/dashboard/overview?plant_id={lab.plant_id}").status_code == 404
    assert other.get("/api/v1/dashboard/overview").json()["gages"]["total"] == 0
