"""permissions.role_map — parse a role map (ROLE_GROUPS: directory group →
role names; ROLE_BOOTSTRAP: subject → role names) into the dict
RoleResolver takes.

Accepted forms:
  - the compact env form "alice=admin|editor,bob=viewer" (spaces ignored);
  - a JSON object string, '{"alice": ["admin", "editor"], "bob": "viewer"}';
  - a mapping, whose values are a list of names or a "a|b" / "a,b" string.
Missing or empty means no entries. Anything else raises ValueError naming
the setting, so a typo surfaces at startup.
"""

import json
from collections.abc import Mapping
from typing import Any

from greentechhub_core.config.readers import setting_value


def _role_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [name.strip() for name in value.replace("|", ",").split(",") if name.strip()]
    return [str(name) for name in value]


def parse_role_map(value: Any, name: str) -> dict[str, list[str]]:
    """`value` (any accepted form) as key → role names. `name` is the
    setting's name, used in the error message."""
    if not value:
        return {}
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{"):
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{name}: not valid JSON: {exc}") from None
        else:
            pairs = {}
            for entry in filter(None, (part.strip() for part in text.split(","))):
                key, sep, roles = entry.partition("=")
                if not sep or not key.strip():
                    raise ValueError(f"{name}: expected 'key=role|role,...', got {entry!r}")
                pairs[key.strip()] = roles.replace("|", ",")
            value = pairs
    if not isinstance(value, Mapping):
        raise ValueError(f"{name}: expected a mapping of key → role names")
    return {str(key): _role_names(roles) for key, roles in value.items()}


def read_role_map(settings: Any, name: str) -> dict[str, list[str]]:
    """The role map `name` ("ROLE_GROUPS" or "ROLE_BOOTSTRAP") on
    `settings`, read with config.readers.setting_value."""
    return parse_role_map(setting_value(settings, name), name)
