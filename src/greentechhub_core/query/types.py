"""types — Filter, Operator, Sort, PageRequest, Page: the pagination/filtering
contract every adapter's query-parameter translation produces and consumes.

greentechhub-core defines these types and the response envelope shape only
(see envelope.py). It does not parse a FastAPI Query(...) or Django's
request.GET — that translation, and the actual paging mechanism, is
adapter-layer. Both adapters produce the same Page envelope, so consumers
render results identically regardless of which backend served the data (see
docs/query.md).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Operator(StrEnum):
    """Comparison/matching operators a Filter's value is applied with.

    A StrEnum (not a plain str Literal): members compare equal to their raw
    string value (Operator.EQ == "eq"), which is convenient for an adapter
    that parses a raw query-string operator name (e.g. "?field=age&op=gte")
    straight into this enum via Operator(raw_value), with no extra mapping
    step of its own.

    docs/query.md's own code sample shows only a partial, explicitly
    ellipsized list ("eq, gt, lt, in, contains, ..."). Everything here beyond
    eq/gt/lt/in/contains is this module's own design call: a standard,
    ORM-lookup-style vocabulary (mirroring the conventional
    exact/gt/gte/lt/lte/in/contains/startswith/endswith/isnull set) chosen to
    cover common REST/ORM-style filtering without growing unboundedly.

    IS_NULL has no separate "is not null" member — a Filter using IS_NULL is
    expected to carry a bool `value` (True = IS NULL, False = IS NOT NULL)
    rather than this enum doubling its own surface area for that distinction.
    """

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"


@dataclass(frozen=True, slots=True, kw_only=True)
class Filter:
    """A single field/operator/value filtering clause.

    Fields:
        field: the field name being filtered on, e.g. "status". Not validated
            against any model/schema here — that's adapter-layer, since only
            the adapter knows what fields actually exist on the resource
            being queried.
        operator: which comparison this filter performs — see Operator.
        value: the operand for `operator`. Typed Any deliberately: its shape
            varies per operator (a single scalar for EQ, a list for IN, a
            bool for IS_NULL, ...) and per field's underlying type — both
            known only to the adapter, never to this generic dataclass.
    """

    field: str
    operator: Operator
    value: Any


@dataclass(frozen=True, slots=True, kw_only=True)
class Sort:
    """A single field/direction sort clause.

    Not shown in docs/query.md's code sample at all (only referenced as
    `sort: list[Sort]`) — this shape is entirely this module's own design
    call. `direction` is a Literal["asc", "desc"] rather than a bare
    `descending: bool`, for self-documentation, consistent with this
    codebase's existing preference for explicit Literal types over bools
    whose meaning requires reading the default (see HealthStatus in
    health/result.py).

    Fields:
        field: the field name being sorted on.
        direction: "asc" (default) or "desc".
    """

    field: str
    direction: Literal["asc", "desc"] = "asc"


@dataclass(frozen=True, slots=True, kw_only=True)
class PageRequest:
    """The requested page: pagination + sorting + filtering, adapter-produced.

    Built by an adapter's query-parameter translation — this module
    only defines the shape, never the parsing (see docs/query.md).

    Fields:
        page: 1-based page number. Defaults to 1 — the universally
            conventional "no page specified" behavior.
        size: items per page. Defaults to 20 as a reasonable general-purpose
            page size; adapters remain free to clamp/override per endpoint.
        sort: ordered list of sort clauses, evaluated left to right. Defaults
            to empty (no explicit sort requested).
        filters: list of filter clauses, implicitly AND-ed together — this
            module takes no position on OR/grouping, which is beyond a plain
            list's expressiveness and would need a richer shape if ever
            needed. Defaults to empty (no filtering requested).

    `sort` and `filters` stay plain `list[...]` (not wrapped immutable) even
    though this dataclass is frozen: their field types are given verbatim by
    docs/query.md's own code sample, and the one confirmed real usage
    constructs these from plain adapter-side lists — honoring that documented
    shape as-is takes priority over this codebase's usual "wrap mutable
    collections invented by this module" convention (contrast VersionInfo in
    version.py, whose wrapped `packages` field is a shape that module
    invented itself, not one handed down by any doc).
    """

    page: int = 1
    size: int = 20
    sort: list[Sort] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class Page[T]:
    """A page of results plus the total count — the shared paginated-response
    envelope every adapter returns, regardless of which framework/paging
    mechanism produced it (see docs/query.md and envelope.py).

    Declared with PEP 695 type-parameter syntax (`class Page[T]`) rather than
    `typing.Generic[T]`: this project's own ruff config (`select` includes
    "UP", `target-version = "py312"`) enforces UP046, which flags
    `Generic[T]` subclassing in favor of PEP 695 syntax on this package's
    Python floor (verified against this repo's exact ruff config/version).
    docs/query.md's own code sample uses `Generic[T]`, but — per this
    codebase's established treatment of that sample as illustrative of
    *fields*, not literally-binding implementation syntax — PEP 695 syntax is
    the correct choice; it produces an identical runtime shape (verified
    empirically: `Page[int](...)` constructs normally, stays frozen, and has
    no `__dict__`, i.e. slots are genuinely in effect).

    Fields:
        items: the page's items, in whatever order the adapter's paging
            mechanism produced.
        total: total number of items across every page (not just this one).
        page: the 1-based page number this Page represents.
        size: the page size that was requested/used.

    No defaults, matching docs/query.md's sample and the one confirmed real
    usage (greentechhub-fastapi's transaction listing), which always supplies
    all four fields explicitly.
    """

    items: list[T]
    total: int
    page: int
    size: int
