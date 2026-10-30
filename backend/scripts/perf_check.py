"""Performance check against a dedicated database (never the production one).

Seeds an organization with N gages (and calibrations / audit rows) by bulk SQL, then times
the main read endpoints and counts SQL statements per request to detect N+1 patterns.

    DATABASE_URL=postgresql+psycopg://.../gagetracker_perf python -m scripts.perf_check --gages 5000
"""

import argparse
import statistics
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.core.db import engine
from app.main import create_app

PW = "Perf-check-2026"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gages", type=int, default=5000)
    ap.add_argument("--repeat", type=int, default=5)
    a = ap.parse_args()
    client = TestClient(create_app())
    email = f"perf-{uuid.uuid4().hex[:6]}@example.com"
    r = client.post("/api/v1/auth/register", json={"organization_name": "[PERF] Org", "plant_code": "P1",
                                                   "plant_name": "Plant", "timezone": "UTC", "full_name": "Perf",
                                                   "email": email, "password": PW})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=h).json()
    org = me["memberships"][0]["organization_id"]
    h["X-Organization-Id"] = org
    plant = client.get("/api/v1/plants", headers=h).json()[0]["id"]
    gt = client.post("/api/v1/gage-types", json={"code": "CAL", "name": "Caliper", "default_frequency_days": 365},
                     headers=h).json()["id"]
    user = me["id"]
    t0 = time.perf_counter()
    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO gages (id, organization_id, gage_code, description, gage_type_id, plant_id, control_status,
                               calibration_frequency_days, last_calibration_date, next_due_date, created_by, updated_by)
            SELECT gen_random_uuid(), :org, 'PG-' || lpad(i::text, 6, '0'), 'Perf gage ' || i, :gt, :plant, 'ACTIVE', 365,
                   current_date - (i % 400), current_date - (i % 400) + 365, :u, :u
            FROM generate_series(1, :n) i"""), {"org": org, "gt": gt, "plant": plant, "u": user, "n": a.gages})
        c.execute(text("""
            INSERT INTO calibration_activities (id, organization_id, plant_id, gage_id, calibration_code, activity_type,
                   status, planned_date, performed_date, result, as_found_in_tolerance, as_left_in_tolerance,
                   created_by, released_at, released_by)
            SELECT gen_random_uuid(), :org, :plant, g.id, 'CALP-' || row_number() over (), 'EXTERNAL_CALIBRATION',
                   'RELEASED', g.last_calibration_date, g.last_calibration_date, 'PASS', true, true, :u, now(), :u
            FROM gages g WHERE g.organization_id = :org"""), {"org": org, "plant": plant, "u": user})
        c.execute(text("""
            INSERT INTO audit_events (id, organization_id, actor_user_id, action, entity_type, entity_id)
            SELECT gen_random_uuid(), :org, :u, 'gage.updated', 'gage', g.id::text
            FROM gages g, generate_series(1, 4) WHERE g.organization_id = :org"""), {"org": org, "u": user})
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        for t in ("gages", "calibration_activities", "audit_events"):
            c.execute(text(f"ANALYZE {t}"))     # what autovacuum does after a bulk load
    print(f"seeded {a.gages} gages, {a.gages} calibrations, {a.gages * 4} audit rows in {time.perf_counter() - t0:.1f}s")

    counter = {"n": 0}
    event.listen(engine, "before_cursor_execute", lambda *args: counter.__setitem__("n", counter["n"] + 1))
    endpoints = [
        "/api/v1/dashboard/overview", "/api/v1/dashboard/summary", "/api/v1/gages?page_size=50",
        "/api/v1/gages?q=PG-0049&page_size=50", "/api/v1/gages?status=OVERDUE&page_size=50",
        "/api/v1/calibrations?page_size=50", "/api/v1/reports/gage_inventory",
        "/api/v1/reports/calibrations_performed", "/api/v1/compliance/matrix", "/api/v1/exchange/gages?page_size=500",
        "/api/v1/audit-events?limit=50",
    ]
    print(f"{'endpoint':55} {'median ms':>10} {'max ms':>8} {'SQL':>5} {'status':>6}")
    for url in endpoints:
        times = []
        for _ in range(a.repeat):
            counter["n"] = 0
            s = time.perf_counter()
            resp = client.get(url, headers=h)
            times.append((time.perf_counter() - s) * 1000)
        print(f"{url:55} {statistics.median(times):10.1f} {max(times):8.1f} {counter['n']:5d} {resp.status_code:6d}")


if __name__ == "__main__":
    main()
