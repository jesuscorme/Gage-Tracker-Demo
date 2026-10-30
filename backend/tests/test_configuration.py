"""Platform configuration: versioned items, custom fields, forms, workflows, approval matrices, business rules."""

import copy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.modules.configuration import workflow
from app.modules.msa.service import DEFAULT_WORKFLOW
from tests.msa_reference import grr_observations
from tests.test_calibration import lab  # noqa: F401
from tests.test_msa import create, msa  # noqa: F401


def propose(actor, kind, definition, summary="change"):
    return actor.post("/api/v1/config/items", json={"kind": kind, "definition": definition,
                                                    "change_summary": summary})


def field(key, **extra):
    return {"entity_type": "gage", "key": key, "label": key.title(), "field_type": "TEXT"} | extra


def test_custom_fields_validation_visibility_and_versions(make_org, gage_type, new_gage):
    admin = make_org("Cfg")
    t = gage_type(admin, "CAL")["id"]
    v1 = propose(admin, "CUSTOM_FIELD", field("supplier_code", text_format="UPPERCASE_CODE", max_length=12))
    assert v1.status_code == 201 and v1.json()["status"] == "ACTIVE" and v1.json()["version"] == 1
    assert propose(admin, "CUSTOM_FIELD", field("ppap_level", field_type="LIST", options=["1", "2", "3"],
                                                required=True)).status_code == 201
    assert propose(admin, "CUSTOM_FIELD", field("customer_owned", field_type="BOOLEAN")).status_code == 201
    r = propose(admin, "CUSTOM_FIELD", field("owner_name", required=True,
                                             visible_when={"field": "customer_owned", "equals": True}))
    assert r.status_code == 201
    # Invalid definitions are rejected (no user regex, built-in names protected).
    assert propose(admin, "CUSTOM_FIELD", field("x1", pattern="(a+)+$")).json()["error"]["code"] == \
        "invalid_configuration"
    assert propose(admin, "CUSTOM_FIELD", field("gage_code")).json()["error"]["code"] == "invalid_configuration"
    assert propose(admin, "CUSTOM_FIELD", field("lvl", field_type="LIST")).json()["error"]["code"] == \
        "invalid_configuration"

    body = {"gage_code": "CF-1", "description": "Caliper", "gage_type_id": t, "plant_id": admin.plant_id}
    r = admin.post("/api/v1/gages", json=body)
    assert r.json()["error"]["code"] == "invalid_custom_fields" and "ppap_level" in r.json()["error"]["details"]
    r = admin.post("/api/v1/gages", json=body | {"custom_fields": {"ppap_level": "4", "supplier_code": "ab c"}})
    assert set(r.json()["error"]["details"]) == {"ppap_level", "supplier_code"}
    # Conditional visibility: owner_name only required when customer_owned is true.
    r = admin.post("/api/v1/gages", json=body | {"custom_fields": {"ppap_level": "3", "customer_owned": True}})
    assert r.json()["error"]["details"] == {"owner_name": "is required"}
    g = admin.post("/api/v1/gages", json=body | {"custom_fields": {"ppap_level": "3", "supplier_code": "SUP-01"}})
    assert g.status_code == 201, g.text
    gid = g.json()["id"]
    assert admin.get(f"/api/v1/custom-fields/gage/{gid}").json() == {"ppap_level": "3", "supplier_code": "SUP-01"}
    r = admin.put(f"/api/v1/custom-fields/gage/{gid}", json={"values": {"ppap_level": None}})
    assert r.json()["error"]["details"] == {"ppap_level": "is required"}
    r = admin.put(f"/api/v1/custom-fields/gage/{gid}", json={"values": {"ppap_level": "2", "unknown": 1}})
    assert r.json()["error"]["details"] == {"unknown": "unknown custom field"}
    assert admin.put(f"/api/v1/custom-fields/gage/{gid}", json={"values": {"ppap_level": "2"}}).status_code == 200
    audit = admin.get(f"/api/v1/audit-events?entity_type=gage&entity_id={gid}").json()
    items = audit["items"] if isinstance(audit, dict) else audit
    assert any(e["action"] == "custom_fields.updated" for e in items)

    # A new version keeps history; the previous one becomes SUPERSEDED.
    v2 = propose(admin, "CUSTOM_FIELD", field("supplier_code", max_length=20), "Allow longer codes").json()
    assert v2["version"] == 2
    item = next(i for i in admin.get("/api/v1/config/items?kind=CUSTOM_FIELD").json() if i["key"] == "gage.supplier_code")
    versions = admin.get(f"/api/v1/config/items/{item['id']}/versions").json()
    assert [v["status"] for v in versions] == ["ACTIVE", "SUPERSEDED"]
    # Forms reference built-in and custom fields only.
    r = propose(admin, "FORM", {"entity_type": "gage", "sections": [
        {"title": "Supplier", "fields": ["supplier_code", "ppap_level", "manufacturer"]}]})
    assert r.status_code == 201
    assert admin.get("/api/v1/forms/gage").json()["sections"][0]["fields"][0] == "supplier_code"
    assert propose(admin, "FORM", {"entity_type": "gage", "sections": [{"title": "X", "fields": ["nope"]}]}) \
        .json()["error"]["code"] == "invalid_configuration"


def test_configuration_versions_need_a_second_approver_and_are_immutable(msa, db):  # noqa: F811
    wf = copy.deepcopy(DEFAULT_WORKFLOW)
    r = propose(msa, "WORKFLOW", wf, "Initial copy")
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"
    vid = r.json()["id"]
    assert propose(msa, "WORKFLOW", wf).json()["error"]["code"] == "draft_pending"
    assert msa.post(f"/api/v1/config/versions/{vid}/approve", json={}).json()["error"]["code"] == \
        "segregation_of_duties"
    tech = msa.tech
    assert tech.post(f"/api/v1/config/versions/{vid}/approve", json={}).status_code == 403
    assert msa.manager.post(f"/api/v1/config/versions/{vid}/reject", json={}).json()["error"]["code"] == \
        "comment_required"
    assert msa.manager.post(f"/api/v1/config/versions/{vid}/approve", json={"comment": "OK"}).json()["status"] == \
        "ACTIVE"
    with pytest.raises(Exception) as exc:
        with db.begin_nested():
            db.execute(text(f"UPDATE config_versions SET definition = '{{}}' WHERE id = '{vid}'"))
    assert "immutable" in str(exc.value)


def test_invalid_workflows_are_rejected(msa):  # noqa: F811
    wf = copy.deepcopy(DEFAULT_WORKFLOW)
    wf["states"] = [s for s in wf["states"] if s["code"] != "APPROVED"]
    errs = propose(msa, "WORKFLOW", wf).json()["error"]["details"]
    assert any("system state 'APPROVED'" in e for e in errs)
    wf = copy.deepcopy(DEFAULT_WORKFLOW)
    wf["states"].append({"code": "ORPHAN", "label": "Orphan", "capabilities": ["fly"]})
    errs = propose(msa, "WORKFLOW", wf).json()["error"]["details"]
    assert any("not reachable" in e for e in errs) and any("unknown capability" in e for e in errs)
    wf = copy.deepcopy(DEFAULT_WORKFLOW)
    wf["transitions"][0]["permission"] = "root:all"
    assert any("unknown permission" in e for e in propose(msa, "WORKFLOW", wf).json()["error"]["details"])


def custom_msa_workflow():
    """Adds a quality sign-off step requiring two distinct approvers and an escalation."""
    wf = copy.deepcopy(DEFAULT_WORKFLOW)
    wf["states"].insert(2, {"code": "QA_SIGNOFF", "label": "Quality sign-off", "capabilities": ["report"]})
    for t in wf["transitions"]:
        if t["code"] == "APPROVE":
            t["from_states"] = ["QA_SIGNOFF"]
    wf["transitions"].append({"code": "TO_QA", "label": "Send to quality", "from_states": ["IN_REVIEW"],
                              "to": "QA_SIGNOFF", "permission": "msa:approve", "action": "REVIEW",
                              "approvals_required": 2})
    wf["transitions"][[t["code"] for t in wf["transitions"]].index("CANCEL")]["from_states"] += ["QA_SIGNOFF"]
    wf["escalations"] = [{"state": "IN_REVIEW", "after_hours": 24, "notify_permission": "msa:approve"}]
    return wf


def test_custom_workflow_votes_rules_matrix_and_escalation(msa, add_user, db):  # noqa: F811
    second = add_user(msa, "metrology_manager")
    vid = propose(msa, "WORKFLOW", custom_msa_workflow(), "Add QA sign-off").json()["id"]
    msa.manager.post(f"/api/v1/config/versions/{vid}/approve", json={})
    # Business rule: a study can only go to review if the GRR is at most 30 %.
    rid = propose(msa, "BUSINESS_RULE", {
        "entity_type": "msa_study", "name": "GRR limit for review", "transitions": ["SUBMIT"],
        "conditions": [{"fact": "pct_sv_grr", "op": "lte", "value": 25}], "message": "GRR above 25 %"}).json()["id"]
    msa.manager.post(f"/api/v1/config/versions/{rid}/approve", json={})
    bad_rule = propose(msa, "BUSINESS_RULE", {
        "entity_type": "msa_study", "name": "bad", "transitions": ["*"],
        "conditions": [{"fact": "__import__", "op": "eq", "value": 1}], "message": "nope"})
    assert bad_rule.json()["error"]["code"] == "invalid_configuration"

    study = create(msa, design={"operators": 3, "parts": 10, "trials": 3})
    assert study["workflow_version"] == 1
    msa.post(f"/api/v1/msa/studies/{study['id']}/observations", json={"observations": grr_observations()})
    msa.post(f"/api/v1/msa/studies/{study['id']}/calculate")
    tr = lambda a, code, c=None: a.post(f"/api/v1/workflows/msa_study/{study['id']}/transitions",  # noqa: E731
                                        json={"transition": code, "comment": c})
    r = tr(msa, "SUBMIT")
    assert r.json()["error"]["code"] == "business_rule_blocked" and r.json()["error"]["details"][0]["version"] == 1
    # New rule version relaxes the limit (26.68 % in the AIAG data).
    rid2 = propose(msa, "BUSINESS_RULE", {
        "entity_type": "msa_study", "name": "GRR limit for review", "transitions": ["SUBMIT"],
        "conditions": [{"fact": "pct_sv_grr", "op": "lte", "value": 30}], "message": "GRR above 30 %"}).json()
    assert rid2["version"] == 2
    msa.manager.post(f"/api/v1/config/versions/{rid2['id']}/approve", json={})
    assert tr(msa, "SUBMIT").json()["state"] == "IN_REVIEW"

    # Escalation after 24 h in review (simulated clock), sent once.
    later = datetime.now(UTC) + timedelta(hours=25)
    assert workflow.escalate_due(db, later) == 1
    assert workflow.escalate_due(db, later) == 0
    kinds = [n["kind"] for n in msa.manager.get("/api/v1/notifications").json()["items"]]
    assert "workflow.escalation" in kinds

    # Approval matrix: only metrology managers may REVIEW msa studies; admin (org_admin) is refused.
    mid = propose(msa, "APPROVAL_MATRIX", {"entity_type": "msa_study",
                                           "actions": {"REVIEW": {"roles": ["metrology_manager"]}}}).json()["id"]
    msa.manager.post(f"/api/v1/config/versions/{mid}/approve", json={})
    assert tr(msa, "TO_QA").json()["error"]["code"] == "approval_matrix_denied"
    # Two distinct approvals are needed for TO_QA.
    first = tr(msa.manager, "TO_QA").json()
    assert first == {"moved": False, "state": "IN_REVIEW", "votes": 1, "required": 2, "warnings": []}
    assert tr(msa.manager, "TO_QA").json()["error"]["code"] == "already_voted"
    assert tr(second, "TO_QA").json()["state"] == "QA_SIGNOFF"
    state = msa.get(f"/api/v1/workflows/msa_study/{study['id']}").json()
    assert state["state"] == "QA_SIGNOFF" and [e["event_type"] for e in state["history"]].count("VOTE") == 2
    assert any(e["event_type"] == "ESCALATION" for e in state["history"])
    # Retiring the custom workflow affects new studies only.
    item = next(i for i in msa.get("/api/v1/config/items?kind=WORKFLOW").json())
    msa.post(f"/api/v1/config/items/{item['id']}/retire", json={"reason": "Back to default"})
    assert create(msa)["workflow_version"] == 0
    assert msa.get(f"/api/v1/workflows/msa_study/{study['id']}").json()["version"] == 1


def test_approval_matrix_applies_to_calibration_and_configuration_permissions(make_org, add_user):
    admin = make_org("Matrix")
    viewer = add_user(admin, "viewer")
    assert viewer.get("/api/v1/config/items").status_code == 403
    auditor = add_user(admin, "auditor")
    assert auditor.get("/api/v1/config/items").status_code == 200
    assert auditor.post("/api/v1/config/items", json={"kind": "CUSTOM_FIELD", "definition": field("a1"),
                                                      "change_summary": "x" * 5}).status_code == 403
    r = propose(admin, "APPROVAL_MATRIX", {"entity_type": "calibration",
                                           "actions": {"APPROVE": {"roles": ["nobody"]}}})
    assert r.json()["error"]["code"] == "invalid_configuration"
    other = make_org("Other")
    item = propose(admin, "CUSTOM_FIELD", field("zz")).json()
    assert other.get(f"/api/v1/config/items/{admin.get('/api/v1/config/items').json()[0]['id']}/versions") \
        .status_code == 404
    assert item["version"] == 1


def test_approval_matrix_restricts_calibration_approval(lab):  # noqa: F811
    from tests.test_calibration import capture_internal, plan, to_in_progress

    vid = propose(lab, "APPROVAL_MATRIX", {"entity_type": "calibration", "actions": {
        "APPROVE": {"roles": ["org_admin"]}}}).json()["id"]
    lab.reviewer.post(f"/api/v1/config/versions/{vid}/approve", json={})
    act = to_in_progress(lab, plan(lab))
    capture_internal(lab, act["id"])
    lab.tech.post(f"/api/v1/calibrations/{act['id']}/submit", json={})
    lab.reviewer.post(f"/api/v1/calibrations/{act['id']}/review", json={"accept": True})
    r = lab.approver.post(f"/api/v1/calibrations/{act['id']}/approve", json={"accept": True})
    assert r.status_code == 403 and r.json()["error"]["code"] == "approval_matrix_denied"
    assert r.json()["error"]["details"]["matrix_version"] == 1
