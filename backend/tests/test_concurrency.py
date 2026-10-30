"""Concurrency with real, separate database connections (committed data, parallel threads)."""

import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.sequences import next_code
from app.main import create_app
from tests.conftest import PASSWORD, TEST_DB


def _run(n, fn):
    out, errors = [None] * n, []
    barrier = threading.Barrier(n)

    def work(i):
        try:
            barrier.wait()
            out[i] = fn(i)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    return out


def _org(client):
    email = f"conc-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"organization_name": "Concurrency", "plant_code": "P1",
                                                   "plant_name": "Plant", "timezone": "UTC", "full_name": "Concurrency admin",
                                                   "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    org = client.get("/api/v1/auth/me", headers=h).json()["memberships"][0]["organization_id"]
    return h | {"X-Organization-Id": org}, uuid.UUID(org)


def test_document_numbers_are_unique_under_concurrency(engine):
    client = TestClient(create_app())          # real sessions, committed transactions
    _, org = _org(client)
    eng = create_engine(TEST_DB, pool_size=20)

    def take(_):
        with Session(eng) as s:
            code = next_code(s, org, "CONC", 2026)
            s.commit()
            return code

    codes = _run(20, take)
    assert sorted(codes) == [f"CONC-2026-{i:05d}" for i in range(1, 21)]
    eng.dispose()


def test_simultaneous_retries_with_one_idempotency_key_create_one_record(engine):
    client = TestClient(create_app())
    headers, org = _org(client)
    gt = client.post("/api/v1/gage-types", json={"code": "CAL", "name": "Caliper", "default_frequency_days": 365},
                     headers=headers).json()["id"]
    plant = client.get("/api/v1/plants", headers=headers).json()[0]["id"]
    body = {"gage_code": "RACE-1", "description": "Concurrent retry", "gage_type_id": gt, "plant_id": plant}
    clients = [TestClient(create_app()) for _ in range(8)]
    codes = _run(8, lambda i: clients[i].post("/api/v1/gages", json=body,
                                              headers=headers | {"Idempotency-Key": "race-key"}).status_code)
    assert set(codes) <= {201, 409} and 201 in codes
    eng = create_engine(TEST_DB)
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM gages WHERE organization_id = :o AND gage_code = 'RACE-1'"),
                      {"o": org}).scalar()
    assert n == 1
    eng.dispose()
