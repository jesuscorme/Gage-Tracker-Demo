"""Multi-tenant isolation: organization A must never read or change data of organization B.

Resources of another tenant are reported as 404 so their existence is not disclosed.
"""

import pytest


@pytest.fixture()
def two_orgs(make_org, gage_type, new_gage):
    a = make_org("Alpha")
    b = make_org("Bravo")
    a.type_id = gage_type(a, "CAL")["id"]
    b.type_id = gage_type(b, "MIC")["id"]
    a.gage = new_gage(a, a.type_id, "A-001")
    b.gage = new_gage(b, b.type_id, "B-001")
    return a, b


def test_list_only_returns_own_gages(two_orgs):
    a, b = two_orgs
    assert [g["gage_code"] for g in a.get("/api/v1/gages").json()["items"]] == ["A-001"]
    assert [g["gage_code"] for g in b.get("/api/v1/gages").json()["items"]] == ["B-001"]
    assert b.get("/api/v1/gages?q=A-001").json()["total"] == 0


def test_cannot_read_update_or_transition_other_tenant_gage(two_orgs):
    a, b = two_orgs
    gid = a.gage["id"]
    for r in (
        b.get(f"/api/v1/gages/{gid}"),
        b.patch(f"/api/v1/gages/{gid}", json={"location": "hijacked"}),
        b.post(f"/api/v1/gages/{gid}/transitions", json={"target": "INACTIVE", "reason": "delete"}),
        b.get(f"/api/v1/gages/{gid}/status-history"),
        b.get(f"/api/v1/gages/{gid}/audit"),
    ):
        assert r.status_code == 404, r.text
    unchanged = a.get(f"/api/v1/gages/{gid}").json()
    assert unchanged["location"] is None and unchanged["control_status"] == "ACTIVE"


def test_cannot_reference_other_tenant_plant_type_or_user(two_orgs):
    a, b = two_orgs
    base = {"gage_code": "X-1", "description": "Probe"}
    r = b.post("/api/v1/gages", json=base | {"gage_type_id": b.type_id, "plant_id": a.plant_id})
    assert r.status_code == 404
    r = b.post("/api/v1/gages", json=base | {"gage_type_id": a.type_id, "plant_id": b.plant_id})
    assert r.status_code == 404
    a_admin_id = a.get("/api/v1/auth/me").json()["id"]
    r = b.post("/api/v1/gages", json=base | {"gage_type_id": b.type_id, "plant_id": b.plant_id,
                                             "responsible_user_id": a_admin_id})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_responsible"


def test_cannot_switch_into_foreign_organization_with_header(two_orgs):
    a, b = two_orgs
    headers = {"Authorization": f"Bearer {b.token}", "X-Organization-Id": a.org_id}
    r = b.client.get("/api/v1/gages", headers=headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "organization_access_denied"


def test_cannot_touch_other_tenant_admin_data(two_orgs):
    a, b = two_orgs
    a_admin_id = a.get("/api/v1/auth/me").json()["id"]
    assert b.patch(f"/api/v1/plants/{a.plant_id}", json={"name": "pwned"}).status_code == 404
    assert b.patch(f"/api/v1/gage-types/{a.type_id}", json={"name": "pwned"}).status_code == 404
    assert b.patch(f"/api/v1/users/{a_admin_id}", json={"is_active": False}).status_code == 404
    assert b.post("/api/v1/departments", json={"plant_id": a.plant_id, "code": "Q", "name": "QA"}).status_code == 404
    assert a.get("/api/v1/plants").json()[0]["name"] == "Alpha Plant 1"
    assert a.get("/api/v1/gages").status_code == 200  # admin of A still active


def test_audit_and_dashboard_are_isolated(two_orgs):
    a, b = two_orgs
    ids = {e["entity_id"] for e in b.get("/api/v1/audit-events?limit=200").json()["items"]}
    assert a.gage["id"] not in ids and a.org_id not in ids
    assert b.get("/api/v1/dashboard/summary").json()["total_in_service"] == 1
    users_b = {u["email"] for u in b.get("/api/v1/users").json()}
    assert a.email not in users_b


def test_same_gage_code_allowed_in_different_organizations(two_orgs, new_gage):
    a, b = two_orgs
    new_gage(b, b.type_id, "A-001")  # same code as Alpha's gage


def test_user_in_two_orgs_must_choose_and_sees_each_separately(client, two_orgs, add_user):
    a, b = two_orgs
    tech = add_user(a, "metrology_technician")
    email = a.get("/api/v1/users").json()
    email = next(u["email"] for u in email if u["id"] == tech.user_id)
    r = b.post("/api/v1/users", json={"email": email, "full_name": "Shared", "password": "Metrology-2026",
                                      "role_code": "viewer"})
    assert r.status_code == 201
    no_header = client.get("/api/v1/gages", headers={"Authorization": f"Bearer {tech.token}"})
    assert no_header.status_code == 422 and no_header.json()["error"]["code"] == "organization_required"
    as_b = client.get("/api/v1/gages", headers={"Authorization": f"Bearer {tech.token}", "X-Organization-Id": b.org_id})
    assert [g["gage_code"] for g in as_b.json()["items"]] == ["B-001"]
    # Viewer role in B: cannot create there even though they are a technician in A.
    r = client.post("/api/v1/gages", headers={"Authorization": f"Bearer {tech.token}", "X-Organization-Id": b.org_id},
                    json={"gage_code": "B-9", "description": "x y", "gage_type_id": b.type_id, "plant_id": b.plant_id})
    assert r.status_code == 403


def test_plant_scope_restricts_within_organization(client, make_org, gage_type, new_gage, add_user):
    admin = make_org("Plants")
    tid = gage_type(admin)["id"]
    p2 = admin.post("/api/v1/plants", json={"code": "P2", "name": "Plant 2"}).json()
    new_gage(admin, tid, "P1-G")
    g2 = new_gage(admin, tid, "P2-G", plant_id=p2["id"])

    tech = add_user(admin, "metrology_technician", plant_ids=[admin.plant_id])
    assert [g["gage_code"] for g in tech.get("/api/v1/gages").json()["items"]] == ["P1-G"]
    assert [p["code"] for p in tech.get("/api/v1/plants").json()] == ["P1"]
    assert tech.get(f"/api/v1/gages/{g2['id']}").status_code == 404
    r = tech.post("/api/v1/gages", json={"gage_code": "P2-NEW", "description": "x y", "gage_type_id": tid,
                                         "plant_id": p2["id"]})
    assert r.status_code == 404
    p1_gage = tech.get("/api/v1/gages").json()["items"][0]
    r = tech.patch(f"/api/v1/gages/{p1_gage['id']}", json={"plant_id": p2["id"]})
    assert r.status_code == 404  # cannot move a gage into a plant outside the user's scope
    assert tech.get("/api/v1/dashboard/summary").json()["total_in_service"] == 1
