import json
import logging

import pytest

from greentechhub_core.logging.setup import configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


def test_configure_logging_emits_json_lines_to_stdout(capsys):
    configure_logging("INFO")
    logging.getLogger("gth.test").info("hello")

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"


def test_log_level_filters_below_configured_level(capsys):
    configure_logging("WARNING")
    logger = logging.getLogger("gth.test.levels")
    logger.info("hidden")
    logger.warning("shown")

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "shown"


def test_configure_logging_accepts_lowercase_level(capsys):
    configure_logging("debug")
    logging.getLogger("gth.test.lower").debug("shown")

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1


def test_configure_logging_is_idempotent(capsys):
    configure_logging("INFO")
    configure_logging("INFO")
    logging.getLogger("gth.test.idempotent").info("only once")

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
