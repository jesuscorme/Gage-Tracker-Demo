"""Gage Tracker Edge Connector - reference agent.

Runs on a PC on the shop floor / laboratory network, next to the instruments. It reads
frames from a source, keeps them in a local SQLite queue (store-and-forward, so readings
survive network or server outages) and forwards them to Gage Tracker with an API key of
an ``edge_agent`` client. Each reading has a unique id, so re-sending after a timeout
never duplicates data (the server ignores already-received ids).

Sources implemented: ``simulator`` (synthetic frames) and ``lines`` (a text file or stdin,
one frame per line, e.g. the output of a serial-to-text bridge). Native serial/USB/BLE
drivers are not implemented in this version.

Usage:
    python edge_agent.py --url https://gagetracker.example.com --key gtk_... --device CAL-ASCII \
        --source lines --input readings.txt
    python edge_agent.py ... --source simulator --nominal 10 --sigma 0.002 --count 25
"""

import argparse
import json
import random
import sqlite3
import sys
import time
import uuid
from datetime import UTC, datetime

import httpx

SCHEMA = """CREATE TABLE IF NOT EXISTS queue (
    reading_uid TEXT PRIMARY KEY, device_code TEXT NOT NULL, raw TEXT NOT NULL, captured_at TEXT NOT NULL,
    sent_at TEXT, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT)"""


class Queue:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.db.commit()

    def add(self, device_code: str, raw: str, captured_at: datetime | None = None) -> str:
        uid = f"{device_code}-{uuid.uuid4().hex}"
        self.db.execute("INSERT INTO queue (reading_uid, device_code, raw, captured_at) VALUES (?, ?, ?, ?)",
                        (uid, device_code, raw.strip(), (captured_at or datetime.now(UTC)).isoformat()))
        self.db.commit()
        return uid

    def pending(self, device_code: str, limit: int = 500) -> list[tuple]:
        return self.db.execute("SELECT reading_uid, raw, captured_at FROM queue WHERE device_code = ? AND sent_at IS "
                               "NULL ORDER BY captured_at LIMIT ?", (device_code, limit)).fetchall()

    def mark(self, uids: list[str], error: str | None) -> None:
        if error:
            self.db.executemany("UPDATE queue SET attempts = attempts + 1, last_error = ? WHERE reading_uid = ?",
                                [(error[:300], u) for u in uids])
        else:
            now = datetime.now(UTC).isoformat()
            self.db.executemany("UPDATE queue SET sent_at = ?, attempts = attempts + 1, last_error = NULL "
                                "WHERE reading_uid = ?", [(now, u) for u in uids])
        self.db.commit()


def flush(queue: Queue, client: httpx.Client, device_code: str, api_key: str) -> dict:
    """Send pending readings in batches. Returns the server's summary or the error."""
    rows = queue.pending(device_code)
    if not rows:
        return {"sent": 0}
    batch = {"device_code": device_code,
             "readings": [{"reading_uid": u, "raw": raw, "captured_at": at} for u, raw, at in rows]}
    uids = [u for u, _, _ in rows]
    try:
        r = client.post("/api/v1/connectors/readings", json=batch, headers={"X-API-Key": api_key})
    except httpx.HTTPError as exc:
        queue.mark(uids, f"network: {exc}")
        return {"sent": 0, "error": str(exc)}
    if r.status_code >= 500 or r.status_code == 429:
        queue.mark(uids, f"HTTP {r.status_code}")
        return {"sent": 0, "error": f"HTTP {r.status_code}"}
    if r.status_code >= 400:
        # Configuration problem (unknown device, revoked key): keep readings, report it.
        queue.mark(uids, f"HTTP {r.status_code}: {r.text[:200]}")
        return {"sent": 0, "error": r.text}
    queue.mark(uids, None)
    return {"sent": len(uids)} | r.json()


def simulator_frames(nominal: float, sigma: float, count: int, unit: str) -> list[str]:
    rng = random.Random()
    return [f"{rng.gauss(nominal, sigma):.4f} {unit}" for _ in range(count)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--queue", default="edge-queue.sqlite3")
    ap.add_argument("--source", choices=["simulator", "lines"], default="lines")
    ap.add_argument("--input", default="-")
    ap.add_argument("--nominal", type=float, default=10.0)
    ap.add_argument("--sigma", type=float, default=0.002)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--unit", default="mm")
    ap.add_argument("--retry-seconds", type=float, default=0, help="keep retrying every N seconds until sent")
    a = ap.parse_args(argv)
    q = Queue(a.queue)
    if a.source == "simulator":
        frames = simulator_frames(a.nominal, a.sigma, a.count, a.unit)
    else:
        stream = sys.stdin if a.input == "-" else open(a.input, encoding="utf-8")
        frames = [line for line in stream if line.strip()]
    for f in frames:
        q.add(a.device, f)
    with httpx.Client(base_url=a.url, timeout=15) as client:
        while True:
            result = flush(q, client, a.device, a.key)
            print(json.dumps(result))
            if "error" not in result or not a.retry_seconds:
                break
            time.sleep(a.retry_seconds)
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
