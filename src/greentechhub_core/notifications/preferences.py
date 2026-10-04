"""notifications.preferences — how each person wants each kind of notice
delivered: in the app, by email, both, or not at all, as one USER setting
per notification category — see docs/modules.md#delivery-preferences.

The categories are the service's own ("sync", "deals"), so they're passed
to a factory, like core's other setting factories. The settings are
ordinary core settings, so the settings page shows them with no extra UI,
and `channels_for` is the check a sender (greentechhub-fastapi's notify)
makes before storing an entry or sending an email.
"""

from collections.abc import Iterable, Mapping

from greentechhub_core.settings import Setting, Settings, SettingScope, SettingType
from greentechhub_core.settings.service import SubjectLike

PREFERENCE_PREFIX = "notify."
"""Every delivery preference's key starts with this: "notify.<category>"."""

DELIVERY_CHOICES = {
    "in_app": "In the app",
    "email": "By email",
    "both": "In the app and by email",
    "off": "Don't notify me",
}
"""The delivery choices, value → label, in the order a form offers them."""

DEFAULT_DELIVERY = "in_app"
"""The choice a category gets unless the service picks another default."""

_CHANNELS = {
    "in_app": frozenset({"in_app"}),
    "email": frozenset({"email"}),
    "both": frozenset({"in_app", "email"}),
    "off": frozenset(),
}


def preference_key(category: str) -> str:
    """The setting key for a category's delivery preference."""
    return PREFERENCE_PREFIX + category


def delivery_channels(choice: str) -> frozenset[str]:
    """The channels ("in_app", "email") a delivery choice means."""
    try:
        return _CHANNELS[choice]
    except KeyError:
        choices = list(DELIVERY_CHOICES)
        raise ValueError(f"delivery must be one of {choices}, got {choice!r}") from None


def _category_pairs(
    categories: Mapping[str, str] | Iterable[str] | Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    if isinstance(categories, Mapping):
        return [(str(c), str(label)) for c, label in categories.items()]
    pairs = []
    for item in categories:
        if isinstance(item, str):
            pairs.append((item, item.replace("_", " ").capitalize()))
        else:
            category, label = item
            pairs.append((str(category), str(label)))
    return pairs


def notification_preferences(
    categories: Mapping[str, str] | Iterable[str] | Iterable[tuple[str, str]],
    *,
    default: str = DEFAULT_DELIVERY,
    group: str = "Notifications",
    help_text: str | None = None,
) -> tuple[Setting, ...]:
    """One USER choice setting per notification category, keyed
    `notify.<category>`, choosing among DELIVERY_CHOICES (default `default`).

    `categories`: category → label, (category, label) pairs, or bare
    categories (labelled from the name: "price_alert" → "Price alert").
    A category is a key segment, so lowercase words joined by underscores;
    anything else fails Setting's key check. ValueError for no categories
    or a default outside DELIVERY_CHOICES.
    """
    if default not in DELIVERY_CHOICES:
        raise ValueError(f"default must be one of {list(DELIVERY_CHOICES)}, got {default!r}")
    pairs = _category_pairs(categories)
    if not pairs:
        raise ValueError("notification_preferences needs at least one category")
    return tuple(
        Setting(
            key=preference_key(category),
            type=SettingType.CHOICE,
            default=default,
            scope=SettingScope.USER,
            label=label,
            help_text=help_text or "",
            choices=DELIVERY_CHOICES,
            group=group,
        )
        for category, label in pairs
    )


def channels_for_sync(
    settings: Settings, identity: SubjectLike | None, category: str
) -> frozenset[str]:
    """The channels `identity` wants for `category`: their own choice, else
    the app's, else the default. A category with no registered preference
    goes to the in-app list."""
    key = preference_key(category)
    if key not in settings.registry:
        return delivery_channels(DEFAULT_DELIVERY)
    return delivery_channels(str(settings.get_sync(key, identity)))


async def channels_for(
    settings: Settings, identity: SubjectLike | None, category: str
) -> frozenset[str]:
    """channels_for_sync, async."""
    key = preference_key(category)
    if key not in settings.registry:
        return delivery_channels(DEFAULT_DELIVERY)
    return delivery_channels(str(await settings.get(key, identity)))
