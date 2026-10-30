"""Security review (block 4): sessions, password policy and recovery, brute force, secrets, headers, files."""

import uuid

from sqlalchemy import text

from tests.conftest import PASSWORD, PDF


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_logout_all_and_password_change_revoke_tokens(client, make_org):
    admin = make_org("Sessions")
    old = admin.headers
    assert client.get("/api/v1/auth/me", headers=old).status_code == 200
    r = client.post("/api/v1/auth/change-password", headers=old,
                    json={"current_password": "wrong-pass-1", "new_password": "Another-pass-2026"})
    assert r.status_code == 401
    r = client.post("/api/v1/auth/change-password", headers=old,
                    json={"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422                                   # policy: length and composition
    r = client.post("/api/v1/auth/change-password", headers=old,
                    json={"current_password": PASSWORD, "new_password": "Another-pass-2026"})
    assert r.status_code == 200
    new = {"Authorization": f"Bearer {r.json()['access_token']}", "X-Organization-Id": admin.org_id}
    assert client.get("/api/v1/auth/me", headers=old).status_code == 401      # previous token revoked
    assert client.get("/api/v1/auth/me", headers=new).status_code == 200
    assert client.post("/api/v1/auth/logout-all", headers=new).status_code == 204
    assert client.get("/api/v1/auth/me", headers=new).status_code == 401
    assert login(client, admin.email, "Another-pass-2026").status_code == 200


def test_brute_force_lockout_and_admin_reset(client, make_org, add_user, db):
    admin = make_org("Lockout")
    tech = add_user(admin, "metrology_technician")
    email = db.execute(text(f"SELECT email FROM users WHERE id = '{tech.user_id}'")).scalar()
    for _ in range(5):
        assert login(client, email, "wrong-password-9").status_code == 401
    r = login(client, email)                                   # even the right password is refused now
    assert r.status_code == 429 and r.json()["error"]["code"] == "too_many_attempts"
    # Only users:manage may issue a reset; the token works once and revokes old sessions.
    assert tech.post(f"/api/v1/users/{tech.user_id}/password-reset").status_code == 403
    issued = admin.post(f"/api/v1/users/{tech.user_id}/password-reset").json()
    stored = db.execute(text("SELECT token_hash FROM password_reset_tokens")).scalars().all()
    assert issued["reset_token"] not in stored
    body = {"token": issued["reset_token"], "new_password": "Fresh-pass-2026"}
    assert client.post("/api/v1/auth/reset-password", json=body).status_code == 204
    assert client.post("/api/v1/auth/reset-password", json=body).json()["error"]["code"] == "invalid_reset_token"
    assert client.get("/api/v1/auth/me", headers=tech.headers).status_code == 401
    assert login(client, email, "Fresh-pass-2026").status_code == 200   # reset clears the lockout window
    assert client.post("/api/v1/auth/reset-password", json={"token": "x" * 30, "new_password": "Fresh-pass-2026"}) \
        .json()["error"]["code"] == "invalid_reset_token"
    other = make_org("Other")
    assert other.post(f"/api/v1/users/{tech.user_id}/password-reset").status_code == 404
    actions = db.execute(text(f"SELECT action FROM audit_events WHERE entity_id = '{tech.user_id}'")).scalars().all()
    assert {"auth.login_failed", "auth.login_locked", "user.password_reset_issued", "auth.password_reset"} <= set(actions)


def test_webhook_secret_encrypted_at_rest(make_org, db):
    admin = make_org("Secrets")
    ep = admin.post("/api/v1/integrations/webhooks", json={"name": "ERP", "url": "http://erp.local/h",
                                                           "event_types": ["gage.created"]}).json()
    stored = db.execute(text(f"SELECT secret FROM webhook_endpoints WHERE id = '{ep['id']}'")).scalar()
    assert stored.startswith("enc:v1:") and ep["secret"] not in stored
    from app.core import crypto
    assert crypto.decrypt(stored) == ep["secret"]


def test_security_headers_and_error_hygiene(client, make_org):
    admin = make_org("Headers")
    r = admin.get("/api/v1/gages")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    r = admin.get(f"/api/v1/gages/{uuid.uuid4()}")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "details", "request_id"}
    assert client.get("/api/v1/gages").status_code == 401
    bad = admin.client.get("/api/v1/gages", headers={"Authorization": "Bearer abc.def.ghi"})
    assert bad.status_code == 401 and "Traceback" not in bad.text


def test_malicious_uploads_and_cross_tenant_documents(make_org, gage_type, new_gage):
    a, b = make_org("Docs A"), make_org("Docs B")
    g = new_gage(a, gage_type(a, "CAL")["id"], "DOC-1")
    up = lambda actor, name, data: actor.post("/api/v1/attachments", data={  # noqa: E731
        "entity_type": "gage", "entity_id": g["id"], "category": "DOCUMENT"}, files={"file": (name, data)})
    assert up(a, "fake.pdf", b"MZ\x90\x00 not a pdf").status_code == 422           # magic bytes
    assert up(a, "script.exe", b"MZ\x90\x00").status_code == 422                   # extension not allowed
    assert up(a, "page.html", b"<script>alert(1)</script>").status_code == 422
    ok = up(a, "cert.pdf", PDF)
    assert ok.status_code == 201
    att = ok.json()["id"]
    assert b.get(f"/api/v1/attachments/{att}/download").status_code == 404
    assert up(b, "cert.pdf", PDF).status_code == 404                              # cannot attach to A's gage
    d = a.get(f"/api/v1/attachments/{att}/download")
    assert d.status_code == 200 and d.headers["Cache-Control"] == "private, no-store"
    events = a.get("/api/v1/audit-events?action=document.downloaded").json()["items"]
    assert len(events) == 1
