"""configure_logging — wires the JSON-emitting root logger every GreenTechHub-ecosystem
service uses.

``import logging`` below resolves to the stdlib module, not this package — Python 3's
import system is absolute-by-default (PEP 328), so a top-level ``logging`` lookup is
unaffected by this file living inside a same-named ``greentechhub_core.logging`` package.
"""

import logging
import sys

from greentechhub_core.logging.formatter import JSONFormatter

_HANDLER_NAME = "greentechhub_core.json_stdout"


def configure_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to emit one JSON object per line to stdout.

    Takes a plain ``log_level`` string rather than a ``GTHBaseSettings`` instance so
    this module stays usable standalone — a CLI, a script, or a test can call
    ``configure_logging("DEBUG")`` directly without importing ``greentechhub_core.config``.
    Adapters pass ``settings.log_level``.

    Safe to call more than once (service startup calling it twice, or once per test):
    it removes only the handler it previously attached (identified by name) before
    adding a new one, so log lines are never emitted twice, and it doesn't disturb
    handlers something else attached to the root logger (e.g. pytest's own log capture).
    """
    root = logging.getLogger()

    for existing in list(root.handlers):
        if getattr(existing, "name", None) == _HANDLER_NAME:
            root.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.name = _HANDLER_NAME
    handler.setFormatter(JSONFormatter())

    root.addHandler(handler)
    root.setLevel(log_level.upper())
