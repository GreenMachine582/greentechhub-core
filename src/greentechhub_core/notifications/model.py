"""notifications.model — Notification: a message stored for one person, in the
shape greentechhub-ui's toast() already uses, so the same notice can be a
toast now and an entry in the notification centre later.

The toast fields are message, kind, title, icon and action {label, url};
duration and variant are presentation, so they aren't stored. `category` is
what M2's delivery preferences key on ("in-app and/or email per category").
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

KINDS = ("success", "info", "warning", "danger", "neutral")
"""The kinds a notification can be: greentechhub-ui's toast kinds."""

KIND_ALIASES = {"warn": "warning", "error": "danger"}
"""Other spellings toast() accepts, and the kind each one means."""


def aware(value: datetime) -> datetime:
    """`value` as a UTC-aware datetime; a naive one is taken to be UTC (some
    databases, SQLite among them, drop the zone on the way back)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalise_kind(kind: str) -> str:
    """A toast kind or alias as one of KINDS; ValueError for anything else."""
    kind = KIND_ALIASES.get(kind, kind)
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS} (or {tuple(KIND_ALIASES)}), got {kind!r}")
    return kind


@dataclass(frozen=True, slots=True, kw_only=True)
class Notification:
    """One stored notice for one person.

    Fields:
        id: unique, minted by new_notification (32 hex characters).
        recipient: who it's for — an Identity.subject.
        message: the text.
        kind: one of KINDS (default "info").
        title, icon: as toast()'s; None when unset.
        action_label, action_url: toast()'s action link, both or neither.
        category: what kind of notice it is, for delivery preferences.
        created_at: when it was made (UTC).
        read_at: when it was marked read (UTC), or None while unread.
    """

    id: str
    recipient: str
    message: str
    kind: str = "info"
    title: str | None = None
    icon: str | None = None
    action_label: str | None = None
    action_url: str | None = None
    category: str = "general"
    created_at: datetime
    read_at: datetime | None = None

    @property
    def read(self) -> bool:
        return self.read_at is not None

    def to_toast(self) -> dict[str, Any]:
        """The toast() detail for this notice: message and kind, plus title,
        icon and action only when set."""
        detail: dict[str, Any] = {"message": self.message, "kind": self.kind}
        if self.title:
            detail["title"] = self.title
        if self.icon:
            detail["icon"] = self.icon
        if self.action_label and self.action_url:
            detail["action"] = {"label": self.action_label, "url": self.action_url}
        return detail


def new_notification(
    recipient: str,
    message: str,
    *,
    kind: str = "info",
    title: str | None = None,
    icon: str | None = None,
    action: Mapping[str, str] | None = None,
    category: str = "general",
    now: datetime | None = None,
) -> Notification:
    """A new, unread Notification with a fresh id. `kind` may be an alias
    ("warn", "error"); `action` is toast()'s {"label", "url"}. ValueError
    for an empty recipient or message, or an unknown kind."""
    if not recipient:
        raise ValueError("a notification needs a recipient")
    if not message:
        raise ValueError("a notification needs a message")
    return Notification(
        id=uuid.uuid4().hex,
        recipient=recipient,
        message=message,
        kind=normalise_kind(kind),
        title=title or None,
        icon=icon or None,
        action_label=(action or {}).get("label") or None,
        action_url=(action or {}).get("url") or None,
        category=category,
        created_at=aware(now or datetime.now(UTC)),
    )


def from_toast(
    recipient: str,
    payload: Mapping[str, Any],
    *,
    category: str = "general",
    now: datetime | None = None,
) -> Notification:
    """A new Notification from a toast() detail, or from the whole
    {"showToast": {...}} HX-Trigger value toast() returns. Presentation keys
    (duration, variant) are dropped."""
    detail = payload.get("showToast", payload)
    return new_notification(
        recipient,
        detail.get("message", ""),
        kind=detail.get("kind", "info"),
        title=detail.get("title"),
        icon=detail.get("icon"),
        action=detail.get("action"),
        category=category,
        now=now,
    )
