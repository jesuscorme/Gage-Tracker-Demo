"""Integrations & Data: API clients, idempotency, webhooks, imports, devices and exchange contracts."""

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

from openpyxl import load_workbook
from sqlalchemy import text

from app.modules.integrations import scheduler, webhooks
from tests.conftest import today
from tests.msa_reference import grr_observations
from tests.test_msa import create, msa  # noqa: F401


def api_client(admin, role="viewer", **extra):
    r = admin.post("/api/v1/integrations/api-clients", json={"name": f"ERP {role}", "role_code": role} | extra)
    assert r.status_code == 201, r.text
    return r.json()


def key_headers(key, org_id=None):
    return {"X-API-Key": key} | ({"X-Organization-Id": org_id} if org_id else {})


# ---------------------------------------------------------------- API clients and exchange contracts

def test_api_key_authentication_scope_and_revocation(client, make_org, gage_type, new_gage, db):
    admin = make_org("API")
    t = gage_type(admin, "CAL")["id"]
    for i in range(3):
        new_gage(admin, t, f"G-{i}")
    other = make_org("Other")
    new_gage(other, gage_type(other, "CAL")["id"], "OTHER-1")
    c = api_client(admin)
    assert c["api_key"].startswith("gtk_") and c["key_prefix"] in c["api_key"]
    stored = db.execute(text(f"SELECT key_hash FROM api_clients WHERE id = '{c['id']}'")).scalar()
    assert stored == hashlib.sha256(c["api_key"].encode()).hexdigest() and c["api_key"] not in stored
    h = key_headers(c["api_key"])
    page = client.get("/api/v1/exchange/gages?page_size=2", headers=h)
    assert page.status_code == 200 and page.headers["X-Contract-Version"] == "1"
    body = page.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["next_page"] == 2
    assert set(body["items"][0]) >= {"id", "gage_code", "status", "next_due_date", "updated_at"}
    page2 = client.get("/api/v1/exchange/gages?page=2&page_size=2", headers=h).json()
    assert page2["next_page"] is None and len(page2["items"]) == 1
    seen = [g["gage_code"] for g in body["items"] + page2["items"]]
    assert sorted(seen) == ["G-0", "G-1", "G-2"]                     # pages partition the result
    since = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    assert client.get("/api/v1/exchange/gages", params={"updated_since": since}, headers=h).json()["total"] == 0
    # Role permissions still apply: a viewer key cannot create gages nor read MSA? (viewer has msa:read).
    r = client.post("/api/v1/gages", json={"gage_code": "X", "description": "xx", "gage_type_id": t,
                                           "plant_id": admin.plant_id}, headers=h)
    assert r.status_code == 403
    assert client.get("/api/v1/exchange/unknown", headers=h).status_code == 404
    # Activity log records the calls.
    log = admin.get(f"/api/v1/integrations/api-clients/{c['id']}/activity").json()
    assert len(log) >= 3 and log[0]["path"].startswith("/api/v1/")
    # Invalid and revoked keys are refused; other organization's admin cannot see the client.
    assert client.get("/api/v1/exchange/gages", headers=key_headers(c["api_key"] + "x")).status_code == 401
    assert other.post(f"/api/v1/integrations/api-clients/{c['id']}/revoke", json={"reason": "x" * 5}) \
        .status_code == 404
    admin.post(f"/api/v1/integrations/api-clients/{c['id']}/revoke", json={"reason": "Rotated"})
    r = client.get("/api/v1/exchange/gages", headers=h)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_api_key"
    r = admin.post("/api/v1/integrations/api-clients", json={"name": "Root", "role_code": "org_admin"})
    assert r.json()["error"]["code"] == "invalid_role"


def test_exchange_contracts_respect_permissions_and_plant_scope(client, make_org, gage_type, new_gage):
    admin = make_org("Scope")
    p2 = admin.post("/api/v1/plants", json={"code": "P2", "name": "Plant 2"}).json()
    t = gage_type(admin, "CAL")["id"]
    new_gage(admin, t, "IN-P1")
    admin.post("/api/v1/gages", json={"gage_code": "IN-P2", "description": "Other plant", "gage_type_id": t,
                                      "plant_id": p2["id"]})
    c = api_client(admin, "requester", plant_ids=[admin.plant_id])
    h = key_headers(c["api_key"])
    codes = {g["gage_code"] for g in client.get("/api/v1/exchange/gages", headers=h).json()["items"]}
    assert codes == {"IN-P1"}
    assert client.get("/api/v1/exchange/msa-studies", headers=h).status_code == 403
    for resource in ("calibrations", "service-requests", "work-orders", "inspection-results", "oot-cases"):
        assert admin.get(f"/api/v1/exchange/{resource}").status_code == 200, resource


# ---------------------------------------------------------------- idempotency

def test_idempotent_retries_do_not_duplicate_records(make_org, gage_type, db):
    admin = make_org("Idem")
    t = gage_type(admin, "CAL")["id"]
    body = {"gage_code": "IDEM-1", "description": "Caliper", "gage_type_id": t, "plant_id": admin.plant_id}
    first = admin.client.post("/api/v1/gages", json=body, headers=admin.headers | {"Idempotency-Key": "abc-1"})
    assert first.status_code == 201
    again = admin.client.post("/api/v1/gages", json=body, headers=admin.headers | {"Idempotency-Key": "abc-1"})
    assert again.status_code == 201 and again.headers.get("Idempotent-Replayed") == "true"
    assert again.json()["id"] == first.json()["id"]
    assert db.execute(text("SELECT count(*) FROM gages WHERE gage_code = 'IDEM-1'")).scalar() == 1
    reused = admin.client.post("/api/v1/gages", json=body | {"description": "Other"},
                               headers=admin.headers | {"Idempotency-Key": "abc-1"})
    assert reused.status_code == 422 and reused.json()["error"]["code"] == "idempotency_key_reused"
    # Without a key the second call is a normal duplicate.
    assert admin.post("/api/v1/gages", json=body).json()["error"]["code"] == "duplicate_gage_code"
    # Errors are stored too (4xx), so a retry gets the same answer.
    bad = admin.client.post("/api/v1/gages", json=body, headers=admin.headers | {"Idempotency-Key": "abc-2"})
    bad2 = admin.client.post("/api/v1/gages", json=body, headers=admin.headers | {"Idempotency-Key": "abc-2"})
    assert bad.status_code == bad2.status_code == 409 and bad2.headers.get("Idempotent-Replayed") == "true"


# ---------------------------------------------------------------- events and webhooks

def test_webhooks_signed_retried_deduplicated_and_dead_lettered(make_org, gage_type, new_gage, db):
    admin = make_org("Hooks")
    r = admin.post("/api/v1/integrations/webhooks", json={"name": "ERP", "url": "http://erp.local/hook",
                                                          "event_types": ["gage.created", "not.an.event"]})
    assert r.json()["error"]["code"] == "invalid_event_types"
    ep = admin.post("/api/v1/integrations/webhooks", json={"name": "ERP", "url": "http://erp.local/hook",
                                                           "event_types": ["gage.created"]}).json()
    assert ep["secret"].startswith("whsec_")
    g = new_gage(admin, gage_type(admin, "CAL")["id"], "HOOK-1")
    calls = []

    def failing(url, headers, body):
        calls.append((url, headers, body))
        return 503

    assert webhooks.enqueue(db, admin_org(admin)) == 1
    assert webhooks.enqueue(db, admin_org(admin)) == 0                  # one delivery per event and endpoint
    now = datetime.now(UTC)
    assert webhooks.dispatch(db, failing, now=now, organization_id=admin_org(admin)) == \
        {"succeeded": 0, "failed": 1, "dead": 0}
    url, headers, body = calls[0]
    expected = webhooks.sign(ep["secret"], headers["X-GageTracker-Timestamp"], body)
    assert headers["X-GageTracker-Signature"] == expected and headers["X-GageTracker-Event"] == "gage.created"
    payload = json.loads(body)
    assert payload["entity_id"] == g["id"] and payload["data"]["gage_code"] == "HOOK-1"
    # Not due yet: nothing is sent; after the backoff it is retried.
    assert webhooks.dispatch(db, failing, now=now + timedelta(seconds=30))["failed"] == 0
    ok = []
    assert webhooks.dispatch(db, lambda u, h, b: ok.append(h) or 200, now=now + timedelta(minutes=2))["succeeded"] == 1
    assert ok[0]["X-GageTracker-Delivery"] == headers["X-GageTracker-Delivery"]   # same delivery id: receiver dedupes
    deliveries = admin.get("/api/v1/integrations/webhook-deliveries").json()
    assert deliveries[0]["status"] == "SUCCEEDED" and deliveries[0]["attempts"] == 2
    attempts = admin.get(f"/api/v1/integrations/webhook-deliveries/{deliveries[0]['id']}/attempts").json()
    assert [a["status_code"] for a in attempts] == [503, 200]

    # A permanently failing endpoint ends in DEAD after the maximum attempts; manual retry re-queues it.
    new_gage(admin, gage_type(admin, "CMM")["id"], "HOOK-2")
    webhooks.enqueue(db, admin_org(admin))
    t = now
    for _ in range(webhooks.MAX_ATTEMPTS):
        t += timedelta(hours=13)
        webhooks.dispatch(db, lambda u, h, b: (_ for _ in ()).throw(ConnectionError("refused")), now=t)
    dead = next(d for d in admin.get("/api/v1/integrations/webhook-deliveries").json() if d["status"] == "DEAD")
    assert dead["attempts"] == webhooks.MAX_ATTEMPTS and "ConnectionError" in dead["last_error"]
    assert admin.post(f"/api/v1/integrations/webhook-deliveries/{dead['id']}/retry").json()["status"] == "PENDING"
    events = admin.get("/api/v1/integrations/events?event_type=gage.created").json()
    assert len(events) == 2


def admin_org(admin):
    import uuid
    return uuid.UUID(admin.org_id)


def test_overdue_scan_emits_once_per_due_date(make_org, gage_type, new_gage, db):
    admin = make_org("Overdue")
    new_gage(admin, gage_type(admin, "CAL", 30)["id"], "OLD-1",
             last_calibration_date=(today() - timedelta(days=90)).isoformat())
    assert scheduler.scan_overdue(db) >= 1
    assert scheduler.scan_overdue(db) == 0
    assert len(admin.get("/api/v1/integrations/events?event_type=gage.overdue").json()) == 1


# ---------------------------------------------------------------- imports

CSV_OK = "Gage ID,Descripcion,Tipo,Planta,Frecuencia\nIMP-1,Caliper 150,CAL,P1,365\nIMP-2,Micrometer,CAL,P1,180\n"


def upload(actor, importer, content, filename="data.csv", **form):
    return actor.post("/api/v1/integrations/imports", data={"importer": importer} | form,
                      files={"file": (filename, content.encode() if isinstance(content, str) else content)})


def test_gage_import_with_mapping_preview_commit_and_history(make_org, gage_type, add_user, db):
    admin = make_org("Import")
    gage_type(admin, "CAL")
    job = upload(admin, "gages", CSV_OK)
    assert job.status_code == 201, job.text
    job = job.json()
    assert job["status"] == "VALIDATED" and job["total_rows"] == 2 and job["error_count"] == 0
    assert job["mapping"] == {"gage_code": "Gage ID", "description": "Descripcion", "gage_type_code": "Tipo",
                              "plant_code": "Planta", "calibration_frequency_days": "Frecuencia"}
    assert job["preview"][0]["gage_code"] == "IMP-1"
    # Validation does not persist anything.
    assert db.execute(text("SELECT count(*) FROM gages WHERE gage_code LIKE 'IMP-%'")).scalar() == 0
    done = admin.post(f"/api/v1/integrations/imports/{job['id']}/commit").json()
    assert done["status"] == "COMMITTED" and done["summary"] == {"applied": 2, "rows": 2}
    assert db.execute(text("SELECT count(*) FROM gages WHERE gage_code LIKE 'IMP-%'")).scalar() == 2
    assert admin.post(f"/api/v1/integrations/imports/{job['id']}/commit").json()["error"]["code"] == "invalid_status"

    # Duplicates in the file and invalid rows are reported per row; nothing is saved.
    bad = upload(admin, "gages", CSV_OK.replace("IMP-1", "IMP-9").replace("IMP-2", "IMP-9")).json()
    assert bad["status"] == "INVALID" and bad["errors"][0]["row"] == 3 and "duplicate" in bad["errors"][0]["errors"][0]
    bad = upload(admin, "gages", "Gage ID,Descripcion,Tipo,Planta\nIMP-3,Caliper,NOPE,P1\nIMP-4,Ok,CAL,P1\n").json()
    assert bad["status"] == "INVALID" and bad["errors"] == [
        {"row": 2, "key": "IMP-3", "errors": ["gage_type_code 'NOPE' does not exist"]}]
    assert admin.post(f"/api/v1/integrations/imports/{bad['id']}/commit").json()["error"]["code"] == "invalid_status"
    assert db.execute(text("SELECT count(*) FROM gages WHERE gage_code IN ('IMP-3','IMP-4','IMP-9')")).scalar() == 0

    # Unmapped required field, then reprocessing the stored file with an explicit mapping.
    odd = upload(admin, "gages", "Code,Text,Kind,Site\nIMP-5,Caliper,CAL,P1\n").json()
    assert odd["status"] == "INVALID" and "is not mapped" in str(odd["errors"])
    fixed = admin.post(f"/api/v1/integrations/imports/{odd['id']}/reprocess", json={"mapping": {
        "gage_code": "Code", "description": "Text", "gage_type_code": "Kind", "plant_code": "Site"}}).json()
    assert fixed["status"] == "VALIDATED" and fixed["reprocess_of_id"] == odd["id"]
    history = admin.get("/api/v1/integrations/imports?importer=gages").json()
    assert len(history) == 5
    tpl = admin.get("/api/v1/integrations/importers/gages/template")
    wb = load_workbook(io.BytesIO(tpl.content))
    assert wb["data"]["A1"].value == "gage_code"
    viewer = add_user(admin, "viewer")
    assert upload(viewer, "gages", CSV_OK).status_code == 403


def test_msa_data_import_uses_the_study_rules(msa):  # noqa: F811
    study = create(msa, design={"operators": 3, "parts": 10, "trials": 3})
    lines = ["Evaluador;Pieza;Replica;Valor"] + [f"{o['operator']};{o['part']};{o['trial']};{o['value']}"
                                                 for o in grr_observations()]
    job = upload(msa, "msa_observations", "\n".join(lines), target_id=study["id"]).json()
    assert job["status"] == "VALIDATED", job["errors"]
    assert msa.get(f"/api/v1/msa/studies/{study['id']}/observations").json() == []
    msa.post(f"/api/v1/integrations/imports/{job['id']}/commit")
    obs = msa.get(f"/api/v1/msa/studies/{study['id']}/observations").json()
    assert len(obs) == 90 and obs[0]["source"] == "IMPORT"
    # Re-importing the same file now collides with existing readings (duplicates), all rows rejected.
    again = upload(msa, "msa_observations", "\n".join(lines), target_id=study["id"]).json()
    assert again["status"] == "INVALID" and again["error_count"] == 90
    assert upload(msa, "msa_observations", "\n".join(lines)).json()["error"]["code"] == "target_required"


# ---------------------------------------------------------------- devices and edge connector

def test_device_readings_simulator_edge_agent_and_idempotency(client, make_org, gage_type, new_gage):
    admin = make_org("Devices")
    g = new_gage(admin, gage_type(admin, "CAL")["id"], "DEV-G1", last_calibration_date=today().isoformat())
    cat = admin.get("/api/v1/integrations/adapters").json()
    assert {a["code"] for a in cat["adapters"]} == {"generic_ascii", "simulator"}
    assert all(a["status"] == "TESTED" for a in cat["adapters"]) and cat["planned_not_supported"]
    sim = admin.post("/api/v1/integrations/devices", json={"device_code": "SIM-1", "name": "Simulator",
                                                           "adapter": "simulator", "plant_id": admin.plant_id,
                                                           "gage_id": g["id"]}).json()
    r = admin.post(f"/api/v1/integrations/devices/{sim['id']}/simulate", json={"nominal": 10, "sigma": 0.002,
                                                                               "count": 10})
    assert r.json()["accepted"] == 10 and r.json()["rejected"] == []
    readings = admin.get(f"/api/v1/integrations/devices/{sim['id']}/readings").json()
    assert len(readings) == 10 and readings[0]["gage_status"] == "CALIBRATED" and readings[0]["unit"] == "mm"
    assert abs(float(readings[0]["value"]) - 10) < 0.02

    caliper = admin.post("/api/v1/integrations/devices", json={"device_code": "CAL-ASCII", "name": "Caliper",
                                                               "adapter": "generic_ascii",
                                                               "plant_id": admin.plant_id, "gage_id": g["id"]}).json()
    agent = api_client(admin, "edge_agent")
    h = key_headers(agent["api_key"])
    batch = {"device_code": "cal-ascii", "readings": [
        {"reading_uid": "r1", "raw": "12.345 mm"}, {"reading_uid": "r2", "raw": "-0,002mm"},
        {"reading_uid": "r3", "raw": "garbage"}]}
    r = client.post("/api/v1/connectors/readings", json=batch, headers=h).json()
    assert r["accepted"] == 2 and r["rejected"][0]["reading_uid"] == "r3"
    r = client.post("/api/v1/connectors/readings", json=batch, headers=h).json()
    assert r["accepted"] == 0 and r["duplicates"] == 2
    vals = sorted(x["value"] for x in admin.get(f"/api/v1/integrations/devices/{caliper['id']}/readings").json())
    assert vals == ["-0.002", "12.345"]
    # The edge agent role can only submit readings.
    assert client.get("/api/v1/integrations/devices", headers=h).status_code == 403
    admin.post(f"/api/v1/gages/{g['id']}/transitions", json={"target": "OUT_OF_SERVICE", "reason": "Damaged"})
    r = client.post("/api/v1/connectors/readings", json={"device_code": "CAL-ASCII", "readings": [
        {"reading_uid": "r9", "raw": "1.000 mm"}]}, headers=h).json()
    assert r["accepted"] == 1 and "OUT_OF_SERVICE" in r["warnings"][0]
    other = make_org("Other")
    assert other.get(f"/api/v1/integrations/devices/{sim['id']}/readings").status_code == 404
