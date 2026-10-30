"""Dedicated background worker (production): ``python -m app.worker``.

Runs the same idempotent jobs as the in-process scheduler (webhook fan-out and delivery,
workflow escalations, overdue scan). Deploy it as its own process/container and set
SCHEDULER_ENABLED=false on the API processes so jobs run in exactly one place.
"""

import logging
import signal
import threading

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.integrations.scheduler import tick

stop = threading.Event()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    log = logging.getLogger("app.worker")
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    log.info("worker_started", extra={"interval": settings.scheduler_interval_seconds})
    while not stop.is_set():
        result = tick()
        log.info("worker_tick", extra={"result": result})
        stop.wait(settings.scheduler_interval_seconds)
    log.info("worker_stopped")


if __name__ == "__main__":
    import app.models  # noqa: F401  (register every model)

    main()
