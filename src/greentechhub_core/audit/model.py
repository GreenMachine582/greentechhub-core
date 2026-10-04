"""audit.model — AuditEntry: one line of who did what, when — see
docs/modules.md#audit-log.

An entry names an actor (an Identity.subject, or None for the system), a
dotted `action` ("stock.archived"), optionally the record it touched
(`target_type`, `target_id`), a human `summary` for a timeline, and JSON
`details`. Details are scrubbed on the way in: any key that looks like a
credential (security.redact.DEFAULT_SECRET_KEYS) has its value replaced, so
an audit trail never holds one.
"""

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from greentechhub_core.security.redact import DEFAULT_SECRET_KEYS
from greentechhub_core.security.throttle import aware

REDACTED = "***REDACTED***"
"""What a scrubbed detail's value becomes (the same marker as redact())."""

_ACTION_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)+")


def check_action(action: str) -> str:
    """`action` if it's dotted lowercase words ("stock.archived"); ValueError
    otherwise. At least two segments, so actions group by their first word."""
    if not _ACTION_PATTERN.fullmatch(action):
        raise ValueError(
            f"invalid audit action {action!r}: expected dotted lowercase words, "
            "e.g. 'stock.archived'"
        )
    return action


def _secret(key: str) -> bool:
    lowered = key.lower()
    return any(secret in lowered for secret in DEFAULT_SECRET_KEYS)


def scrub(value: Any) -> Any:
    """`value` with every credential-like key's value replaced by REDACTED,
    through nested mappings and lists."""
    if isinstance(value, Mapping):
        return {
            str(k): (REDACTED if _secret(str(k)) else scrub(v)) for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [scrub(v) for v in value]
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditEntry:
    """One recorded action.

    Fields:
        id: unique, minted by new_entry (32 hex characters).
        at: when it happened (UTC).
        actor: who did it (an Identity.subject), or None for the system.
        action: dotted lowercase words, e.g. "stock.archived".
        target_type, target_id: the record it touched ("stock", "42"), or
            both None.
        summary: the line a timeline shows, e.g. "Archived ASX:BHP".
        details: extra JSON data (before/after values, counts), scrubbed.
    """

    id: str
    at: datetime
    action: str
    actor: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    summary: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


def new_entry(
    action: str,
    *,
    actor: str | None = None,
    target: tuple[str, Any] | None = None,
    summary: str = "",
    details: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> AuditEntry:
    """A new AuditEntry with a fresh id. `target` is (type, id); the id is
    stored as a string. ValueError for a malformed action, a target missing
    its type or id, or details that aren't JSON-serialisable."""
    check_action(action)
    target_type = target_id = None
    if target is not None:
        target_type, raw_id = target
        if not target_type or raw_id is None or str(raw_id) == "":
            raise ValueError("an audit target needs both a type and an id")
        target_id = str(raw_id)
    clean = scrub(dict(details or {}))
    try:
        json.dumps(clean)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"audit details must be JSON-serialisable: {exc}") from None
    return AuditEntry(
        id=uuid.uuid4().hex,
        at=aware(now or datetime.now(UTC)),
        action=action,
        actor=actor or None,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        details=clean,
    )
