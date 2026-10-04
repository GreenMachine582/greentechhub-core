"""greentechhub_core.notifications — notices stored per person for
greentechhub-ui's notification centre; see docs/modules.md#notifications."""

from greentechhub_core.notifications.model import (
    KIND_ALIASES,
    KINDS,
    Notification,
    from_toast,
    new_notification,
    normalise_kind,
)
from greentechhub_core.notifications.preferences import (
    DEFAULT_DELIVERY,
    DELIVERY_CHOICES,
    PREFERENCE_PREFIX,
    channels_for,
    channels_for_sync,
    delivery_channels,
    notification_preferences,
    preference_key,
)
from greentechhub_core.notifications.store import InMemoryNotificationStore, NotificationStore

__all__ = [
    "DEFAULT_DELIVERY",
    "DELIVERY_CHOICES",
    "InMemoryNotificationStore",
    "KINDS",
    "KIND_ALIASES",
    "Notification",
    "NotificationStore",
    "PREFERENCE_PREFIX",
    "channels_for",
    "channels_for_sync",
    "delivery_channels",
    "from_toast",
    "new_notification",
    "normalise_kind",
    "notification_preferences",
    "preference_key",
]
