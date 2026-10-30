"""MSA Management: studies, capture, calculation through the engine, criteria, versioning, workflow, reports."""

import pytest
from sqlalchemy import text

from tests.conftest import today
from tests.msa_reference import GRR_AIAG_AR, grr_observations


@pytest.fixture()
def msa(make_org, gage_type, add_user, new_gage, authorize):
    admin = make_org("MSA")
    admin.me = admin.get("/api/v1/auth/me").json()["id"]
    admin.type_id = gage_type(admin, "CAL", 365)["id"]
    admin.gage = new_gage(admin, admin.type_id, "MIC-01", last_calibration_date=today().isoformat())
    admin.manager = add_user(admin, "metrology_manager")
    admin.tech = add_user(admin, "metrology_technician")
    authorize(admin, admin.me, "MSA_EVALUATION")
    return admin


def create(msa, method="GRR_CROSSED_AR", design=None, params=None, **extra):
    body = {"title": "Bore diameter GRR", "method": method, "characteristic": "Bore 10.00 +/- 0.05",
            "part_number": "PN-10", "plant_id": msa.plant_id, "gage_id": msa.gage["id"],
            "responsible_id": msa.me, "start_date": today().isoformat(), "design": design or {},
            "params": params or {}} | extra
    r = msa.post("/api/v1/msa/studies", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def add(msa, study, rows):
    return msa.post(f"/api/v1/msa/studies/{study['id']}/observations", json={"observations": rows})


def move(actor, study, code, comment=None):
    return actor.post(f"/api/v1/workflows/msa_study/{study['id']}/transitions",
                      json={"transition": code, "comment": comment})


def grr_criteria(msa, approver, method="GRR_CROSSED_AR", **extra):
    tpl = next(t for t in msa.get("/api/v1/msa/criteria/templates").json() if method in t["methods"])
    r = msa.post("/api/v1/msa/criteria", json={"name": "Corporate GRR", "method": method,
                                               "scope": "ORGANIZATION", "rules": tpl["rules"],
                                               "source": tpl["source"]} | extra)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["status"] == "DRAFT" and c["version"] == 1
    r = approver.post(f"/api/v1/msa/criteria/{c['id']}/approve")
    assert r.status_code == 200, r.text
    return r.json()


def test_grr_study_end_to_end_with_versioned_criteria_and_report(msa, db):
    study = create(msa, design={"operators": 3, "parts": 10, "trials": 3, "tolerance": 4.0, "unit": "mm"})
    assert study["study_code"].startswith(f"MSA-{today().year}-") and study["status"] == "DRAFT"
    assert len(msa.get(f"/api/v1/msa/studies/{study['id']}/sequence").json()) == 90
    v = msa.get(f"/api/v1/msa/studies/{study['id']}/validation").json()
    assert v["valid"] is False and v["planned"] == 90 and v["issues"][0]["code"] == "no_data"
    assert add(msa, study, grr_observations()).status_code == 201
    assert msa.get(f"/api/v1/msa/studies/{study['id']}/validation").json() == {
        "valid": True, "issues": [], "observations": 90, "planned": 90}

    # Without approved criteria the result is statistical only: no acceptance decision.
    run1 = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate")
    assert run1.status_code == 201, run1.text
    run1 = run1.json()
    assert run1["decision"] == "NO_CRITERIA" and run1["criteria_snapshot"] is None
    assert run1["algorithm_version"] == "1.0.0" and run1["engine_version"] == "1.0.0"
    assert run1["validation_status"] == "VALIDATED" and len(run1["input_hash"]) == 64
    m = run1["results"]["metrics"]
    assert m["pct_sv_grr"] == pytest.approx(GRR_AIAG_AR["pct_grr"], abs=0.01) and m["ndc"] == 5
    assert m["pct_tolerance_grr"] == pytest.approx(100 * 6 * m["grr"] / 4.0)
    assert run1["gage_snapshot"]["gage_code"] == "MIC-01"

    grr_criteria(msa, msa.manager)
    run2 = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()
    assert run2["run_number"] == 2 and run2["decision"] == "CONDITIONAL"
    assert run2["criteria_snapshot"]["name"] == "Corporate GRR" and run2["criteria_snapshot"]["version"] == 1
    statuses = {(e["metric"], e["value"]): e["status"] for e in run2["evaluation"]}
    assert statuses[("pct_sv_grr", 30)] == "PASS" and statuses[("pct_sv_grr", 10)] == "CONDITIONAL"
    assert statuses[("ndc", 5)] == "PASS"
    # The first run is unchanged by later criteria.
    assert msa.get(f"/api/v1/msa/runs/{run1['id']}").json()["decision"] == "NO_CRITERIA"
    ver = msa.post(f"/api/v1/msa/runs/{run1['id']}/verify").json()
    assert ver["identical"] is True and ver["input_hash_matches"] is True

    # Workflow: submit -> conclusion -> approve (segregation of duties).
    assert move(msa, study, "SUBMIT").json()["state"] == "IN_REVIEW"
    assert move(msa.manager, study, "APPROVE").json()["error"]["code"] == "conclusion_required"
    r = msa.manager.post(f"/api/v1/msa/studies/{study['id']}/conclusion", json={"decision": "ACCEPTABLE"})
    assert r.json()["error"]["code"] == "comment_required"          # differs from computed CONDITIONAL
    r = msa.manager.post(f"/api/v1/msa/studies/{study['id']}/conclusion",
                         json={"decision": "CONDITIONAL", "comment": "Use limited to final inspection"})
    assert r.json()["final_decision"] == "CONDITIONAL"
    assert move(msa, study, "APPROVE").json()["error"]["code"] == "segregation_of_duties"
    done = move(msa.manager, study, "APPROVE").json()
    assert done["state"] == "APPROVED" and done["moved"] is True
    s = msa.get(f"/api/v1/msa/studies/{study['id']}").json()
    assert s["status"] == "APPROVED" and s["end_date"] == today().isoformat() and s["latest_decision"] == "CONDITIONAL"
    # Approved studies cannot take more data or be recalculated.
    assert add(msa, study, [{"operator": "A", "part": "1", "trial": 4, "value": 1}]).json()["error"]["code"] == \
        "state_not_allowed"
    assert msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()["error"]["code"] == "state_not_allowed"

    rep = msa.post(f"/api/v1/msa/studies/{study['id']}/reports", json={"run_id": run2["id"]})
    assert rep.status_code == 201, rep.text
    rep = rep.json()
    pdf = msa.get(f"/api/v1/attachments/{rep['attachment_id']}/download")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 3000
    assert msa.get(f"/api/v1/msa/studies/{study['id']}/reports").json()[0]["revision"] == 1
    payload = db.execute(text("SELECT payload FROM outbox_events WHERE event_type = 'msa.study_completed'")).scalar()
    assert payload["data"]["decision"] == "CONDITIONAL" and payload["data"]["algorithm_version"] == "1.0.0"
    assert msa.get(f"/api/v1/msa/studies?gage_id={msa.gage['id']}").json()[0]["id"] == study["id"]


def test_runs_criteria_and_observations_are_immutable_in_the_database(msa, db):
    study = create(msa, design={"operators": 3, "parts": 10, "trials": 3})
    add(msa, study, grr_observations())
    run = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()
    crit = grr_criteria(msa, msa.manager)
    for sql in (f"UPDATE msa_runs SET decision = 'ACCEPTABLE' WHERE id = '{run['id']}'",
                f"DELETE FROM msa_runs WHERE id = '{run['id']}'",
                f"UPDATE msa_criteria_sets SET rules = '[]' WHERE id = '{crit['id']}'",
                f"UPDATE msa_observations SET value = 99 WHERE study_id = '{study['id']}'"):
        with pytest.raises(Exception) as exc:
            with db.begin_nested():
                db.execute(text(sql))
        assert "immutable" in str(exc.value) or "versioned" in str(exc.value) or "append-only" in str(exc.value)
    # A new criteria version keeps the name and increments the version; self-approval is refused.
    r = msa.post("/api/v1/msa/criteria", json={"name": "Corporate GRR", "method": "GRR_CROSSED_AR",
                                               "scope": "ORGANIZATION", "source": "Rev 2",
                                               "rules": [{"metric": "pct_sv_grr", "op": "lte", "value": 20}]})
    assert r.json()["version"] == 2
    assert msa.post(f"/api/v1/msa/criteria/{r.json()['id']}/approve").json()["error"]["code"] == \
        "segregation_of_duties"
    r = msa.post("/api/v1/msa/criteria", json={"name": "Bad", "method": "GRR_CROSSED_AR", "scope": "ORGANIZATION",
                                               "source": "x" * 5, "rules": [{"metric": "cgk", "op": "gte",
                                                                             "value": 1.33}]})
    assert r.json()["error"]["code"] == "invalid_criteria"


def test_corrections_supersede_and_stale_results_block_submission(msa):
    study = create(msa, method="TYPE1", design={"reference": 10.0, "tolerance": 0.1, "resolution": 0.001})
    rows = [{"trial": i + 1, "value": v} for i, v in enumerate(
        [10.002, 9.998, 10.001, 9.999, 10.0, 10.003, 9.997, 10.001, 9.999, 10.0])]
    created = add(msa, study, rows).json()
    # Whole batch rejected on a duplicate; nothing saved.
    r = add(msa, study, [{"trial": 11, "value": 10.0}, {"trial": 3, "value": 10.0}])
    assert r.json()["error"]["code"] == "invalid_observations"
    assert len(msa.get(f"/api/v1/msa/studies/{study['id']}/observations").json()) == 10
    run = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()
    assert run["results"]["metrics"]["cg"] == pytest.approx(0.02 / (6 * (30e-6 / 9) ** 0.5), rel=1e-6)
    # Correct one reading: the original is kept as superseded.
    r = msa.post(f"/api/v1/msa/observations/{created[0]['id']}/correct",
                 json={"reason": "Transcription error", "replacement": {"value": 10.001}})
    assert r.status_code == 200 and r.json()["supersedes_id"] == created[0]["id"]
    allrows = msa.get(f"/api/v1/msa/studies/{study['id']}/observations?include_superseded=true").json()
    assert len(allrows) == 11 and sum(o["superseded"] for o in allrows) == 1
    assert move(msa, study, "SUBMIT").json()["error"]["code"] == "stale_results"
    run2 = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()
    assert run2["input_hash"] != run["input_hash"]
    assert move(msa, study, "SUBMIT").json()["state"] == "IN_REVIEW"
    assert move(msa.manager, study, "RETURN").json()["error"]["code"] == "comment_required"
    assert move(msa.manager, study, "RETURN", "Add 15 readings").json()["state"] == "DRAFT"


def test_invalid_designs_are_reported_and_never_calculated(msa):
    r = msa.post("/api/v1/msa/studies", json={
        "title": "Bad AR", "method": "GRR_CROSSED_AR", "characteristic": "x", "plant_id": msa.plant_id,
        "gage_id": msa.gage["id"], "responsible_id": msa.me, "start_date": today().isoformat(),
        "design": {"operators": 4, "trials": 3}})
    assert r.json()["error"]["code"] == "invalid_design"
    study = create(msa, method="GRR_CROSSED_ANOVA", design={"operators": 3, "parts": 10, "trials": 3})
    add(msa, study, grr_observations()[:-5])
    r = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_design"
    codes = {i["code"] for i in r.json()["error"]["details"]}
    assert "missing_observation" in codes
    assert msa.get(f"/api/v1/msa/studies/{study['id']}/runs").json() == []
    # Attribute study rejects numeric values and unknown categories at capture.
    att = create(msa, method="ATTRIBUTE_AGREEMENT", design={"categories": ["G", "NG"]})
    r = add(msa, att, [{"operator": "A", "part": "1", "trial": 1, "category": "MAYBE"}])
    assert r.json()["error"]["code"] == "invalid_observations"


def test_calculation_requires_permission_and_personal_authorization(msa, add_user):
    study = create(msa, method="BIAS", design={"reference": 6.0})
    add(msa, study, [{"trial": i + 1, "value": v} for i, v in enumerate([5.9, 6.1, 6.0, 6.0, 6.2, 5.8])])
    assert msa.tech.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()["error"]["code"] == "not_authorized"
    viewer = add_user(msa, "viewer")
    assert viewer.post(f"/api/v1/msa/studies/{study['id']}/calculate").status_code == 403
    assert viewer.get(f"/api/v1/msa/studies/{study['id']}").status_code == 200
    run = msa.post(f"/api/v1/msa/studies/{study['id']}/calculate").json()
    assert run["method"] == "BIAS" and any("at least 10" in w for w in run["results"]["warnings"])


def test_unusable_gage_blocks_capture_and_studies_are_isolated(msa, make_org):
    study = create(msa, method="BIAS", design={"reference": 6.0})
    msa.post(f"/api/v1/gages/{msa.gage['id']}/transitions", json={"target": "OUT_OF_SERVICE", "reason": "Damaged"})
    r = add(msa, study, [{"trial": 1, "value": 6.0}])
    assert r.json()["error"]["code"] == "gage_unavailable"
    other = make_org("Other")
    assert other.get(f"/api/v1/msa/studies/{study['id']}").status_code == 404
    assert other.post(f"/api/v1/workflows/msa_study/{study['id']}/transitions",
                      json={"transition": "CANCEL", "comment": "x"}).status_code == 404


def test_criteria_resolution_prefers_customer_then_plant(msa):
    def approved(name, **scope):
        rules = [{"metric": "pct_sv_grr", "op": "lte", "value": {"Org": 30, "Plant": 20, "Cust": 5}[name]}]
        c = msa.post("/api/v1/msa/criteria", json={"name": name, "method": "GRR_CROSSED_ANOVA", "rules": rules,
                                                   "source": "Internal procedure", **scope}).json()
        return msa.manager.post(f"/api/v1/msa/criteria/{c['id']}/approve").json()

    approved("Org", scope="ORGANIZATION")
    approved("Plant", scope="PLANT", plant_id=msa.plant_id)
    approved("Cust", scope="CUSTOMER", customer="ACME")
    s1 = create(msa, method="GRR_CROSSED_ANOVA")
    s2 = create(msa, method="GRR_CROSSED_ANOVA", customer="acme")
    for s in (s1, s2):
        add(msa, s, grr_observations())
    r1 = msa.post(f"/api/v1/msa/studies/{s1['id']}/calculate").json()
    r2 = msa.post(f"/api/v1/msa/studies/{s2['id']}/calculate").json()
    assert r1["criteria_snapshot"]["name"] == "Plant" and r1["decision"] == "NOT_ACCEPTABLE"
    assert r2["criteria_snapshot"]["name"] == "Cust" and r2["decision"] == "NOT_ACCEPTABLE"


def test_attribute_and_stability_studies_through_the_api(msa):
    att = create(msa, method="ATTRIBUTE_AGREEMENT", design={
        "categories": ["G", "NG"], "part_reference": {"1": "G", "2": "NG", "3": "G"},
        "accept_category": "G", "reject_category": "NG"})
    rows = [{"operator": o, "part": p, "trial": t, "category": c}
            for o in "AB" for t in (1, 2) for p, c in (("1", "G"), ("2", "NG"), ("3", "G"))]
    add(msa, att, rows)
    run = msa.post(f"/api/v1/msa/studies/{att['id']}/calculate").json()
    assert run["results"]["metrics"]["min_effectiveness_pct"] == 100.0
    assert run["results"]["metrics"]["fleiss_kappa_between"] == pytest.approx(1.0)
    stab = create(msa, method="STABILITY", design={"subgroup_size": 1, "reference": 5.0},
                  params={"rules": {"2": {"enabled": True, "run": 8}}})
    add(msa, stab, [{"subgroup": i + 1, "trial": 1, "value": 5 + (0.01 if i % 2 else -0.01)} for i in range(20)])
    run = msa.post(f"/api/v1/msa/studies/{stab['id']}/calculate").json()
    assert run["results"]["metrics"]["stable"] is True and run["results"]["design"]["rules"]["2"]["run"] == 8
