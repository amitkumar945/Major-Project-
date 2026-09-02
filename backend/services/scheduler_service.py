"""
Background SLA sweep.

`escalation_service.run_sla_check()` is what actually escalates an overdue
complaint. It has always been reachable from the admin screen
(POST /api/admin/sla-check); this module additionally runs it on a timer, so a
deployment that nobody is sitting in front of still escalates on time instead
of waiting for someone to press a button.

Design notes:

* OFF unless SLA_AUTO_CHECK=true, so an existing deployment behaves exactly as
  it did before this file existed.
* A plain `threading.Timer` chain - no APScheduler, no Celery, no Redis. This
  is a single-process campus deployment and the job is one Mongo scan an hour.
* The thread is a daemon, so it never keeps a shutting-down server alive.
* Every run is wrapped: a failing sweep logs and reschedules rather than
  killing the thread, because a scheduler that dies silently after one bad
  night is worse than no scheduler at all.
* `run_sla_check()` is idempotent, so a duplicate run is harmless.

Behind multiple workers (gunicorn -w 4) each worker would start its own timer.
That is safe - the sweep only escalates a complaint whose level is actually
due to rise - but wasteful, so prefer one worker, or leave this off and drive
the endpoint from cron / Windows Task Scheduler instead.
"""

import logging
import threading

logger = logging.getLogger(__name__)

# Module-level so a second create_app() in the same process (the test-suite
# builds several) cannot leave two timers running.
_timer = None
_lock = threading.Lock()


def _run_once(app) -> None:
    """One sweep, inside an application context, swallowing any failure."""
    from services import escalation_service

    try:
        with app.app_context():
            result = escalation_service.run_sla_check()
        logger.info(
            "Scheduled SLA check: %s checked, %s escalated, %s warned.",
            result.get("checked", 0), result.get("escalated", 0), result.get("warned", 0),
        )
    except Exception:
        # A database blip must not kill the scheduler thread for good.
        logger.exception("Scheduled SLA check failed; will try again next interval.")


def _schedule(app, interval_seconds: int) -> None:
    global _timer

    def tick():
        _run_once(app)
        _schedule(app, interval_seconds)  # chain the next run

    with _lock:
        _timer = threading.Timer(interval_seconds, tick)
        _timer.daemon = True  # never block interpreter shutdown
        _timer.name = "sla-check"
        _timer.start()


def start(app) -> bool:
    """Start the periodic sweep if it is enabled. Returns whether it started."""
    if not app.config.get("SLA_AUTO_CHECK"):
        return False

    minutes = app.config.get("SLA_CHECK_INTERVAL_MINUTES", 60)
    try:
        minutes = max(1, int(minutes))  # a zero/negative interval would spin
    except (TypeError, ValueError):
        minutes = 60

    stop()  # never run two chains at once

    # The first sweep waits one interval rather than firing during startup, so
    # boot stays fast and a restart loop cannot hammer the database.
    _schedule(app, minutes * 60)
    logger.info("SLA auto-check enabled: every %s minute(s).", minutes)
    return True


def stop() -> None:
    """Cancel the pending sweep, if any. Safe to call when nothing is running."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None
