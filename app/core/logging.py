"""Logging setup shared by the API and the worker.
JSON lines in production, readable text locally, with the request id on every line."""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import AppEnv, Settings
from app.core.middleware import get_request_id

TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
NO_REQUEST_ID = "-"
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or NO_REQUEST_ID
        return True


class JsonFormatter(logging.Formatter):
    # Render a log record as one JSON line
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", NO_REQUEST_ID),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# Send all logs to stdout in one format: JSON in production, text otherwise
def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if settings.app_env == AppEnv.PRODUCTION:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    # same format for uvicorn's logs (its access log is off; the middleware logs requests)
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
