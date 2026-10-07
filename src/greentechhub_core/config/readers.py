"""config.readers — read the adapter settings (AUTH_ADAPTER,
CORS_ALLOWED_ORIGINS, TRUSTED_PROXIES, ROLE_GROUPS, ROLE_BOOTSTRAP) off a
service's settings object, tolerantly, the same way in every adapter.

GTHBaseSettings declares them as lowercase fields (`trusted_proxies`, …). A
service's own SCREAMING_CASE attribute, declared or set at runtime (e.g.
CORS_ALLOWED_ORIGINS="*" in development), comes first when it's non-empty;
otherwise the lowercase field. Both read the same env var, so they only
differ after a runtime change, and GTHBaseSettings' non-empty defaults
(auth_adapter="local") mustn't hide that. Any object works, not only a
GTHBaseSettings.

A list setting is a comma-separated string (the natural shape for an env
var, e.g. "https://a.example,https://b.example") or an already-parsed
list/tuple. Missing or empty means an empty list: safe out of the box, not
a startup crash.
"""

from collections.abc import Sequence
from typing import Any


def setting_value(settings: Any, name: str) -> Any:
    """`name` (e.g. "TRUSTED_PROXIES") from `settings`: the SCREAMING_CASE
    attribute when it's non-empty, else the lowercase field; None if
    neither is set."""
    for attribute in (name.upper(), name.lower()):
        if value := getattr(settings, attribute, None):
            return value
    return None


def read_list_setting(settings: Any, name: str) -> list[str]:
    """`name` as a list of non-empty, stripped strings."""
    value = setting_value(settings, name)
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return []


def read_str_setting(settings: Any, name: str, default: str) -> str:
    """`name` as a string, or `default` when it's unset or empty."""
    value = setting_value(settings, name)
    if not value:
        return default
    return str(value)
