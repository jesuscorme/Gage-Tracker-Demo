"""Edge Connector reference agent: store-and-forward against the real API (in-process)."""

import importlib.util
import pathlib

import httpx

from tests.conftest import today

AGENT = pathlib.Path(__file__).resolve().parents[2] / "edge" / "edge_agent.py"
spec = importlib.util.spec_from_file_location("edge_agent", AGENT)
edge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edge)


class Down(httpx.Client):
    def post(self, *a, **kw):
        raise httpx.ConnectError("network unreachable")


def test_agent_buffers_offline_and_forwards_once(client, make_org, gage_type, new_gage, tmp_path):
    admin = make_org("Edge")
    g = new_gage(admin, gage_type(admin, "CAL")["id"], "EDGE-G", last_calibration_date=today().isoformat())
    admin.post("/api/v1/integrations/devices", json={"device_code": "MIC-7", "name": "Micrometer", "adapter":
                                                     "generic_ascii", "plant_id": admin.plant_id, "gage_id": g["id"]})
    key = admin.post("/api/v1/integrations/api-clients", json={"name": "Lab PC", "role_code": "edge_agent"}).json()
    q = edge.Queue(str(tmp_path / "q.sqlite3"))
    for raw in ("25.001 mm", "25.003 mm", "24.999 mm"):
        q.add("MIC-7", raw)
    # Network down: nothing is lost.
    assert edge.flush(q, Down(), "MIC-7", key["api_key"])["sent"] == 0
    assert len(q.pending("MIC-7")) == 3
    # Back online: the queue is forwarded, then empty.
    r = edge.flush(q, client, "MIC-7", key["api_key"])
    assert r["sent"] == 3 and r["accepted"] == 3
    assert q.pending("MIC-7") == [] and edge.flush(q, client, "MIC-7", key["api_key"]) == {"sent": 0}
    # A resend of the same ids (e.g. lost acknowledgement) is ignored by the server.
    q.db.execute("UPDATE queue SET sent_at = NULL")
    q.db.commit()
    assert edge.flush(q, client, "MIC-7", key["api_key"])["duplicates"] == 3
    # A revoked key keeps the readings queued and reports the error.
    admin.post(f"/api/v1/integrations/api-clients/{key['id']}/revoke", json={"reason": "PC replaced"})
    q.add("MIC-7", "25.000 mm")
    assert "error" in edge.flush(q, client, "MIC-7", key["api_key"]) and len(q.pending("MIC-7")) == 1
