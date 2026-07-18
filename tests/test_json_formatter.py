import datetime as dt
import json
import logging
import sys

from greentechhub_core.logging.context import reset_request_id, set_request_id
from greentechhub_core.logging.formatter import JSONFormatter


def _make_record(*, level=logging.INFO, msg="hello", args=(), exc_info=None):
    return logging.LogRecord(
        name="greentechhub.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def test_produces_valid_json_with_expected_fields():
    record = _make_record(msg="hello %s", args=("world",))
    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "greentechhub.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
    assert "request_id" not in payload
    assert "exception" not in payload


def test_timestamp_is_iso8601_utc_with_z_suffix():
    payload = json.loads(JSONFormatter().format(_make_record()))
    assert payload["timestamp"].endswith("Z")
    dt.datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))


def test_includes_request_id_when_set():
    token = set_request_id("req-123")
    try:
        payload = json.loads(JSONFormatter().format(_make_record()))
        assert payload["request_id"] == "req-123"
    finally:
        reset_request_id(token)


def test_omits_request_id_when_unset():
    payload = json.loads(JSONFormatter().format(_make_record()))
    assert "request_id" not in payload


def test_includes_exception_when_exc_info_true():
    try:
        raise ValueError("boom")
    except ValueError:
        record = _make_record(level=logging.ERROR, msg="failed", exc_info=sys.exc_info())

    payload = json.loads(JSONFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]


def test_omits_exception_field_when_no_exc_info():
    payload = json.loads(JSONFormatter().format(_make_record()))
    assert "exception" not in payload
