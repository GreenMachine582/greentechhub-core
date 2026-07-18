"""permissions.catalogue — Permission (a validated "resource.action" string)
and Role (a named bundle of Permissions) — the typed vocabulary every
service builds its own permission catalogue from.

See docs/permissions.md: this module intentionally does not enumerate or
store any actual permission values (no "PORTFOLIO_VIEW = ..." lives here) —
"portfolio.view", "import.run", "reports.view" are worked examples from the
doc, not members this package defines. Each service owns its own full
catalogue (a plain module of Permission constants built via `permission()`)
and its own grants (looked up from that service's own storage); this module
only supplies the typed building block and typo-safety, never a shared
registry. A module-level dict/set tracking "every Permission ever
constructed" would silently recreate exactly the "three places defining the
same thing" duplication docs/permissions.md calls out — deliberately not
built here.
"""

import re
from dataclasses import dataclass
from typing import Self

_SEGMENT_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class Permission(str):
    """A validated "resource.action" permission string — see
    docs/permissions.md's own convention. A `str` subclass (not
    `typing.NewType`): NewType is purely a static-typing alias with zero
    runtime behavior (its "constructor" is an identity function — it cannot
    validate anything), while every consuming service's permission
    catalogue is exactly the kind of open-ended, per-service-defined
    vocabulary that still needs shape validation (does this look like a
    `resource.action` string) even though the *set of valid values* is
    unbounded and this package can never enumerate it. Operator's StrEnum
    precedent (query/types.py) doesn't fit here for that reason: a StrEnum
    validates against a fixed, closed membership set at parse time, and
    there is no closed set to validate a Permission's value against — only
    its shape. A `str` subclass keeps every `str` behavior (`==`, hashing,
    dict-key use, f-string formatting, `isinstance(p, str)`) while still
    being a distinguishable type for signatures, and giving this module one
    place — `__new__` — to enforce that shape.

    Validation (enforced in `__new__`, the single entry point every
    Permission goes through — whether constructed directly, via the
    `permission()` factory below, or indirectly through Role's own element
    coercion; there is deliberately no separate "unchecked" construction
    path):
      - exactly two dot-separated segments (`resource.action`) — zero dots
        or more than one dot (which would make a constructed Permission's
        `resource`/`action` parts ambiguous to recover) are both rejected.
      - each segment is non-empty and matches `[A-Za-z0-9_]+` —
        alphanumeric plus underscore, a conservative default matching
        common identifier conventions shared across the languages/tools
        this ecosystem touches, rather than allowing every character a
        `resource.action` string could theoretically contain.

    Case is not constrained: docs/permissions.md's own examples
    ("portfolio.view") are lowercase by convention, but enforcing case here
    would be exactly the kind of opinionated policy this codebase's
    generic primitives avoid baking in (see security.redact's
    caller-extensible key list) — a service is free to use whatever casing
    convention it likes, as long as the two-segment/allowed-character shape
    holds.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> Self:
        parts = value.split(".")
        if len(parts) != 2 or not all(_SEGMENT_PATTERN.fullmatch(part) for part in parts):
            raise ValueError(
                f"invalid permission string {value!r}: expected 'resource.action' "
                "shape, each segment non-empty and alphanumeric/underscore only"
            )
        return super().__new__(cls, value)


def permission(resource: str, action: str) -> Permission:
    """Build a validated Permission from separate `resource`/`action` parts —
    a convenience over `Permission(f"{resource}.{action}")` for the common
    case of declaring a catalogue entry from two already-separate names
    (e.g. `PORTFOLIO_VIEW = permission("portfolio", "view")`).

    Delegates entirely to Permission's own `__new__` for validation (joins
    the two parts with "." and constructs a Permission from the result)
    rather than validating `resource`/`action` independently here — a
    `resource` containing an embedded dot (e.g. `permission("a.b", "view")`)
    still gets caught, because the joined string then splits into three
    parts, which Permission's shape check rejects. Keeping exactly one
    validation code path means this factory and a bare
    `Permission("portfolio.view")` call can never disagree about what's
    valid.
    """
    return Permission(f"{resource}.{action}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Role:
    """A named bundle of Permissions — docs/permissions.md's own example:
    `Trader = {portfolio.view, portfolio.edit, reports.view}`. Purely a
    grouping convenience a service defines for itself (e.g. one module of
    Role constants alongside its Permission catalogue); this package does
    not interpret Role specially anywhere else — `has_permission` (see
    check.py) only ever checks a single Permission against a flat `granted`
    collection, never a Role, by design: a service reads `.permissions` off
    whichever Role(s) apply and unions them into its own flat granted set
    (e.g. `granted = trader_role.permissions | extra_perms`) before calling
    has_permission.

    Fields:
        name: the role's own display/identity label (e.g. "Trader") —
            purely descriptive, not interpreted by this package.
        permissions: the bundle's members. Accepts any iterable at
            construction (a set literal, list, tuple, generator — matching
            security.redact's own extra_keys: Sequence[str] precedent of
            taking a plain iterable rather than demanding a specific
            container already built) via `__post_init__` coercion; stored
            as a frozenset[Permission] once constructed — deduplicated and
            fit for O(1) membership testing when a service unions it into
            its own granted set. Each element is passed back through
            Permission() during coercion (not merely wrapped as-is), so a
            Role built from plain strings still gets the same shape
            validation a Permission built through the factory would — there
            is no way to end up with an unvalidated string living inside a
            Role's `permissions`.
    """

    name: str
    permissions: frozenset[Permission]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "permissions", frozenset(Permission(p) for p in self.permissions)
        )
