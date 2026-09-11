"""JSONFormatter — one JSON object per log line, shaped for the homelab's Loki/Alloy
log-scraping pipeline (Alloy tails container stdout; Loki itself imposes no field-name
contract, so the field names below are this package's own convention).
"""

import datetime as dt
import json
import logging

from greentechhub_core.logging.context import get_request_id


class JSONFormatter(logging.Formatter):
    """Formats each ``LogRecord`` as a single-line JSON object.

    Fields:
        timestamp: UTC time the record was created, ISO 8601 with millisecond
            precision and a trailing ``Z`` (e.g. ``"2026-07-18T12:34:56.789Z"``).
        level: the record's level name (e.g. ``"INFO"``).
        logger: the logger name (``record.name``).
        message: the rendered log message (``record.getMessage()``, i.e. after
            ``%``-style argument substitution).
        service, version: this process's own identity — the same
            ``service.name``/``service.version`` pair
            ``observability.resource.get_resource_attributes`` produces for OTel,
            included only when the formatter was constructed with them (see
            ``configure_logging``'s own ``service``/``version`` parameters) —
            omitted entirely, not emitted as ``null``, for a service that hasn't
            opted in, same precedent as ``request_id`` below.
        request_id: the current request ID from ``context.get_request_id()``, included
            only when set — omitted entirely (rather than emitted as ``null``) so Loki
            queries filtering on the field's presence aren't polluted by requestless
            log lines (startup, background jobs).
        exception: a formatted traceback string, included only when the record carries
            exception info (``record.exc_info`` truthy) — e.g. ``logger.error(...,
            exc_info=True)`` or ``logger.exception(...)``.
    """

    def __init__(self, *, service: str | None = None, version: str | None = None) -> None:
        super().__init__()
        self._service = service
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "timestamp": _isoformat_utc(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self._service is not None:
            payload["service"] = self._service
        if self._version is not None:
            payload["version"] = self._version

        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def _isoformat_utc(epoch_seconds: float) -> str:
    return (
        dt.datetime.fromtimestamp(epoch_seconds, tz=dt.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
