"""envelope — serializing a Page into a plain, JSON-serializable dict.

docs/query.md describes this file only as "shared paginated-response shape",
and no confirmed usage anywhere exercises it — the one real consumption
example imports Page directly from types.py and returns it as-is, relying on
its consuming framework to serialize the dataclass itself. Page already *is*
the shared envelope shape per docs/query.md's own prose, so this module
doesn't redefine it — it provides a serialization helper for an adapter that
instead needs a plain dict response body (e.g. a view layer that isn't already
dataclass-aware, or a place a JSON response is hand-built directly).
"""

from typing import Any

from greentechhub_core.query.types import Page


def total_pages(total: int, size: int) -> int:
    """Total number of pages, rounding up (ceiling division).

    Returns 0 when `size <= 0` rather than raising ZeroDivisionError — an
    adapter computing this from a possibly-unvalidated PageRequest.size
    shouldn't have to guard against a crash here; "0 pages" is a reasonable
    answer for "no valid page size was given" either way.
    """
    if size <= 0:
        return 0
    return -(-total // size)  # ceiling division without importing math


def to_envelope(page: Page[Any]) -> dict[str, Any]:
    """Convert a Page into a plain JSON-serializable dict.

    Adds a computed `pages` field (via total_pages) alongside the four
    documented Page fields — useful for an adapter that needs a plain-dict
    response body rather than one that can serialize the Page dataclass
    directly. `items` is passed through unchanged: Page is generic over T, so
    this function has no way to know how to serialize an arbitrary T itself
    (e.g. calling .model_dump() on each item) — that step belongs to the
    adapter, which does know.
    """
    return {
        "items": page.items,
        "total": page.total,
        "page": page.page,
        "size": page.size,
        "pages": total_pages(page.total, page.size),
    }
