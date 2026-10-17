"""Celery app and worker configuration.
Redis is the broker; results are stored in Postgres, not Celery."""

from typing import Any

from celery import Celery, signals

from app.core.config import get_settings
from app.core.logging import setup_logging

CELERY_APP_NAME = "support_tickets"
TASKS_MODULE = "app.worker.tasks"
SERIALIZER = "json"
PROCESS_TICKET_TASK = "tickets.process_ticket"
REQUEST_ID_HEADER_KEY = "request_id"

_settings = get_settings()

celery_app = Celery(CELERY_APP_NAME, broker=_settings.redis_url, include=[TASKS_MODULE])
celery_app.conf.update(
    task_ignore_result=True,
    # requeue the message if a worker dies mid-task
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer=SERIALIZER,
    accept_content=[SERIALIZER],
    # give up quickly if Redis is down so API requests don't hang
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5},
)


@signals.setup_logging.connect
def _configure_worker_logging(**_: Any) -> None:
    setup_logging(get_settings())


@signals.worker_process_init.connect
def _dispose_engine_after_fork(**_: Any) -> None:
    # prefork only: a forked child must not reuse the parent's connections
    from app.db.session import engine

    engine.dispose(close=False)
