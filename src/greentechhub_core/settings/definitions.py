"""settings.definitions — SettingScope, SettingType and Setting: the frozen
definition of one runtime setting — see docs/settings.md.

A Setting describes a value; it holds none. Values live in a store (a later
item) and are resolved against the definition by resolution.py. Everything
a store or form hands back goes through `Setting.validate` (typed values) or
`Setting.coerce` (form strings) first, so a definition is the one place that
decides what a valid value is.

This module doesn't import permissions/: `edit_permission` is a plain string.
A permissions.Permission is a `str` subclass, so passing one works as-is.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

_KEY_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)*")

TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
FALSE_VALUES = frozenset({"false", "0", "no", "off"})
"""Form/env strings `coerce` accepts for a BOOL setting, case-insensitive —
the same sets feature_flags.provider accepts ("on" is also what an HTML
checkbox posts)."""


class SettingScope(StrEnum):
    """Who a setting's value belongs to.

    APP settings have one value for the whole service, changed by an admin.
    USER settings have a value per person; the app value then acts as the
    admin-set default for everyone who hasn't chosen their own.
    """

    APP = "app"
    USER = "user"


class SettingType(StrEnum):
    BOOL = "bool"
    INT = "int"
    STR = "str"
    CHOICE = "choice"


SettingValue = bool | int | str


def _choice_pairs(choices: Mapping[str, str] | Iterable[str] | Iterable[tuple[str, str]]):
    if isinstance(choices, Mapping):
        return tuple((str(value), str(label)) for value, label in choices.items())
    pairs = []
    for choice in choices:
        if isinstance(choice, str):
            pairs.append((choice, choice))
        else:
            value, label = choice
            pairs.append((str(value), str(label)))
    return tuple(pairs)


@dataclass(frozen=True, slots=True, kw_only=True)
class Setting:
    """One runtime setting's definition.

    Fields:
        key: dotted, lowercase identifier, e.g. "ui.page_size". Segments are
            `[a-z0-9]` words joined by single underscores, so the env var
            name derived from a key (resolution.env_var_name) is unambiguous.
        type: bool, int, str or choice.
        default: the value used when nothing else is set. Validated like any
            other value, so a bad default fails at definition time.
        scope: SettingScope.APP or SettingScope.USER.
        label / help_text / group: what a settings form shows. `group`
            clusters settings under one heading; "" means ungrouped.
        choices: CHOICE only, required there. Accepts a value → label
            mapping, bare values (the label is the value), or (value, label)
            pairs; stored as a tuple of (value, label) pairs in the given
            order, which is the order a form lists them in.
        min / max: INT only, both optional and inclusive.
        edit_permission: the permission string needed to change the
            app-level value. `None` means the definition asks for none;
            the Settings facade (a later item) enforces it.

    Construction fails fast with ValueError on a malformed key, choices or
    bounds on the wrong type, empty or duplicate choices, min > max, or a
    default that doesn't validate.
    """

    key: str
    type: SettingType
    default: SettingValue
    scope: SettingScope
    label: str
    help_text: str = ""
    choices: tuple[tuple[str, str], ...] = ()
    min: int | None = None
    max: int | None = None
    group: str = ""
    edit_permission: str | None = None

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError(
                f"invalid setting key {self.key!r}: expected lowercase dotted segments, "
                "e.g. 'ui.page_size'"
            )
        object.__setattr__(self, "type", SettingType(self.type))
        object.__setattr__(self, "scope", SettingScope(self.scope))
        object.__setattr__(self, "choices", _choice_pairs(self.choices))
        if self.type is SettingType.CHOICE:
            values = [value for value, _ in self.choices]
            if not values:
                raise ValueError(f"setting {self.key!r}: a choice setting needs choices")
            if len(set(values)) != len(values):
                raise ValueError(f"setting {self.key!r}: duplicate choice values")
        elif self.choices:
            raise ValueError(f"setting {self.key!r}: only a choice setting takes choices")
        if self.type is not SettingType.INT and (self.min is not None or self.max is not None):
            raise ValueError(f"setting {self.key!r}: only an int setting takes min/max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"setting {self.key!r}: min {self.min} is above max {self.max}")
        try:
            self.validate(self.default)
        except ValueError as exc:
            raise ValueError(f"setting {self.key!r}: invalid default: {exc}") from None

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(value for value, _ in self.choices)

    def validate(self, value: object) -> SettingValue:
        """Return `value` if it's a valid typed value for this setting, else
        raise ValueError. No conversion: an int setting rejects "5" and
        True (bool is an int subclass), a bool setting rejects 1. Use
        `coerce` for strings from a form or env var.
        """
        match self.type:
            case SettingType.BOOL:
                if not isinstance(value, bool):
                    raise ValueError(f"expected a bool, got {value!r}")
            case SettingType.INT:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"expected an int, got {value!r}")
                if self.min is not None and value < self.min:
                    raise ValueError(f"{value} is below the minimum {self.min}")
                if self.max is not None and value > self.max:
                    raise ValueError(f"{value} is above the maximum {self.max}")
            case SettingType.STR:
                if not isinstance(value, str):
                    raise ValueError(f"expected a str, got {value!r}")
            case SettingType.CHOICE:
                if not isinstance(value, str) or value not in self.choice_values:
                    raise ValueError(f"{value!r} is not one of {list(self.choice_values)}")
        return value

    def coerce(self, raw: str) -> SettingValue:
        """Convert a string (a form field or env var) to a validated typed
        value, raising ValueError when it can't. Bools accept TRUE_VALUES /
        FALSE_VALUES; ints are parsed after stripping whitespace; str and
        choice values are taken as given.
        """
        match self.type:
            case SettingType.BOOL:
                lowered = raw.strip().lower()
                if lowered in TRUE_VALUES:
                    return True
                if lowered in FALSE_VALUES:
                    return False
                raise ValueError(f"expected a yes/no value, got {raw!r}")
            case SettingType.INT:
                try:
                    value = int(raw.strip())
                except ValueError:
                    raise ValueError(f"expected a whole number, got {raw!r}") from None
                return self.validate(value)
            case _:
                return self.validate(raw)
