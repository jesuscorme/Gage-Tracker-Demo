"""Health checks, error envelope, migrations and authentication."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text

import app.models  # noqa: F401
from app.core.db import Base
from app.modules.identity.models import Role
from app.modules.identity.permissions import PERMISSIONS, SYSTEM_ROLES
from tests.conftest import PASSWORD


# ---------------------------------------------------------------- health & errors


def test_health_live_and_ready(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["schema_revision"] == "0011_security"


def test_request_id_is_returned(client):
    r = client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_error_envelope_for_unknown_route(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found" and body["request_id"]


def test_validation_error_envelope(client):
    r = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------- migrations & seeds


def test_models_match_migrations(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_seeded_roles_match_permission_catalogue(db):
    assert set(db.scalars(text("SELECT code FROM permissions"))) == set(PERMISSIONS)
    for role in db.scalars(select(Role)):
        assert {p.code for p in role.permissions} == set(SYSTEM_ROLES[role.code]["permissions"]), role.code


def test_audit_trail_is_append_only(db, make_org):
    make_org("Append")
    event_id = db.execute(text("SELECT id FROM audit_events LIMIT 1")).scalar()
    for stmt in ("UPDATE audit_events SET action = 'tampered' WHERE id = :i",
                 "DELETE FROM audit_events WHERE id = :i"):
        with pytest.raises(Exception, match="append-only"):
            with db.begin_nested():
                db.execute(text(stmt), {"i": event_id})


# ---------------------------------------------------------------- authentication


def test_register_creates_org_plant_admin_and_audit(client, make_org):
    admin = make_org("Acme Stamping")
    me = admin.get("/api/v1/auth/me").json()
    m = me["memberships"][0]
    assert m["role_code"] == "org_admin" and m["organization_name"] == "Acme Stamping"
    assert "gages:release" in m["permissions"]
    plants = admin.get("/api/v1/plants").json()
    assert [p["code"] for p in plants] == ["P1"]
    actions = {e["action"] for e in admin.get("/api/v1/audit-events").json()["items"]}
    assert {"organization.created", "plant.created", "user.registered"} <= actions


def test_register_rejects_duplicate_email_and_weak_password(client, make_org):
    admin = make_org()
    base = {"organization_name": "Other", "plant_code": "P1", "plant_name": "Plant", "full_name": "X Y",
            "timezone": "UTC"}
    r = client.post("/api/v1/auth/register", json=base | {"email": admin.email, "password": PASSWORD})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    r = client.post("/api/v1/auth/register", json=base | {"email": "new@example.com", "password": "short"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/register", json=base | {"email": "new@example.com", "password": "onlyletterslong"})
    assert r.status_code == 422


def test_register_rejects_unknown_timezone(client):
    r = client.post("/api/v1/auth/register", json={
        "organization_name": "TZ", "plant_code": "P1", "plant_name": "Plant", "full_name": "X Y",
        "timezone": "Mars/Olympus", "email": "tz@example.com", "password": PASSWORD,
    })
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_timezone"


def test_login_success_and_failure(client, make_org):
    admin = make_org()
    ok = client.post("/api/v1/auth/login", json={"email": admin.email.upper(), "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["token_type"] == "bearer"
    bad = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "Wrong-password-1"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert unknown.status_code == 401
    actions = [e["action"] for e in admin.get("/api/v1/audit-events?entity_type=user").json()["items"]]
    assert "auth.login_failed" not in actions  # failed logins carry no tenant, they are platform events


def test_protected_endpoints_require_valid_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/gages", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"


def test_update_profile_language(make_org):
    admin = make_org()
    r = admin.patch("/api/v1/auth/me", json={"preferred_language": "en"})
    assert r.status_code == 200 and r.json()["preferred_language"] == "en"
    assert admin.patch("/api/v1/auth/me", json={"preferred_language": "fr"}).status_code == 422
