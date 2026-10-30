"""Background jobs: webhook fan-out and delivery, workflow escalations, overdue scan.

Runs in a daemon thread of the API process (one tick every SCHEDULER_INTERVAL_SECONDS).
Every job is idempotent, so running several API processes only repeats no-ops; a
dedicated worker process is the production target (see docs/integrations).
"""

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.configuration import workflow
from app.modules.events import service as events
from app.modules.gages.models import Gage
from app.modules.gages.status import ControlStatus
from app.modules.integrations import webhooks
from app.modules.organizations.models import Organization

logger = logging.getLogger("app.scheduler")


def scan_overdue(db) -> int:
    """Emit gage.overdue once per gage and due date (dedupe key)."""
    emitted = 0
    for org in db.scalars(select(Organization).where(Organization.is_active.is_(True))):
        today = datetime.now(ZoneInfo(org.timezone)).date()
        for g in db.scalars(select(Gage).where(Gage.organization_id == org.id, Gage.next_due_date < today,
                                               Gage.control_status == ControlStatus.ACTIVE.value)):
            if events.emit(db, org.id, "gage.overdue", "gage", g.id,
                           {"gage_code": g.gage_code, "next_due_date": g.next_due_date, "plant_id": g.plant_id},
                           dedupe_key=f"gage.overdue:{g.id}:{g.next_due_date.isoformat()}"):
                emitted += 1
    db.commit()
    return emitted


def tick() -> dict:
    out = {}
    with SessionLocal() as db:
        for name, job in (("overdue", scan_overdue), ("enqueued", webhooks.enqueue),
                          ("delivered", webhooks.dispatch), ("escalations", workflow.escalate_due)):
            try:
                out[name] = job(db)
            except Exception:
                db.rollback()
                logger.exception("scheduler_job_failed", extra={"job": name})
    return out


class Scheduler:
    def __init__(self, interval: int):
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="gt-scheduler", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.interval):
            tick()
