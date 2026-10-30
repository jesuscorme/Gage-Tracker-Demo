"""Role-based access control enforced by the backend."""

import pytest


@pytest.fixture()
def org(make_org, gage_type):
    admin = make_org("RBAC")
    admin.type_id = gage_type(admin)["id"]
    return admin


@pytest.mark.parametrize(
    "role,can_create,can_read_audit,can_manage_users,can_manage_types",
    [
        ("org_admin", True, True, True, True),
        ("metrology_manager", True, True, False, True),
        ("metrology_technician", True, False, False, False),
        ("auditor", False, True, False, False),
        ("viewer", False, False, False, False),
    ],
)
def test_permissions_by_role(org, add_user, role, can_create, can_read_audit, can_manage_users, can_manage_types):
    user = add_user(org, role)
    assert user.get("/api/v1/gages").status_code == 200

    r = user.post("/api/v1/gages", json={"gage_code": f"R-{role}", "description": "Caliper",
                                         "gage_type_id": org.type_id, "plant_id": org.plant_id})
    assert r.status_code == (201 if can_create else 403)
    if not can_create:
        assert r.json()["error"]["details"]["required_permission"] == "gages:create"

    assert user.get("/api/v1/audit-events").status_code == (200 if can_read_audit else 403)
    r = user.post("/api/v1/users", json={"email": f"x-{role}@example.com", "full_name": "X Y",
                                         "password": "Metrology-2026", "role_code": "viewer"})
    assert r.status_code == (201 if can_manage_users else 403)
    r = user.post("/api/v1/gage-types", json={"code": f"T{role[:3]}", "name": "Type"})
    assert r.status_code == (201 if can_manage_types else 403)


def test_viewer_cannot_change_status_or_edit(org, add_user, new_gage):
    gage = new_gage(org, org.type_id)
    viewer = add_user(org, "viewer")
    assert viewer.patch(f"/api/v1/gages/{gage['id']}", json={"location": "X"}).status_code == 403
    r = viewer.post(f"/api/v1/gages/{gage['id']}/transitions", json={"target": "OUT_OF_SERVICE", "reason": "test"})
    assert r.status_code == 403


def test_unknown_role_is_rejected(org):
    r = org.post("/api/v1/users", json={"email": "u@example.com", "full_name": "U U",
                                        "password": "Metrology-2026", "role_code": "superuser"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_role"


def test_role_change_takes_effect_immediately(org, add_user):
    tech = add_user(org, "metrology_technician")
    assert tech.get("/api/v1/audit-events").status_code == 403
    assert org.patch(f"/api/v1/users/{tech.user_id}", json={"role_code": "auditor"}).status_code == 200
    assert tech.get("/api/v1/audit-events").status_code == 200


def test_deactivated_member_loses_access(org, add_user):
    tech = add_user(org, "metrology_technician")
    assert org.patch(f"/api/v1/users/{tech.user_id}", json={"is_active": False}).status_code == 200
    r = tech.get("/api/v1/gages")
    assert r.status_code == 403 and r.json()["error"]["code"] == "organization_access_denied"


def test_last_admin_cannot_be_removed(org):
    me = org.get("/api/v1/auth/me").json()
    r = org.patch(f"/api/v1/users/{me['id']}", json={"role_code": "viewer"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "last_admin"
    r = org.patch(f"/api/v1/users/{me['id']}", json={"is_active": False})
    assert r.status_code == 422
    assert org.get("/api/v1/gages").status_code == 200


def test_user_management_is_audited(org, add_user):
    tech = add_user(org, "metrology_technician")
    org.patch(f"/api/v1/users/{tech.user_id}", json={"role_code": "viewer"})
    events = org.get(f"/api/v1/audit-events?entity_type=user&entity_id={tech.user_id}").json()["items"]
    actions = [e["action"] for e in events]
    assert "user.added" in actions and "user.membership_updated" in actions
    changed = next(e for e in events if e["action"] == "user.membership_updated")
    assert changed["changes"]["role"] == ["metrology_technician", "viewer"]
