"""contracts.query — PageContract: shared conformance coverage verifying an
adapter's real pagination path produces a Page whose to_envelope() output
agrees with core's own total_pages() computation — see docs/testing.md.

A concrete subclass supplies one fixture:
    page: a Page[Any] built by the adapter's *real* pagination path — its
        own Query(...)-parameter parsing fed into an actual paginated query
        — not a hand-built `Page(...)` literal. core has no visibility into
        any adapter's own query-param parsing (that's adapter-layer, per
        docs/query.md), so this contract can't drive that first hop itself;
        requiring a fixture built from the adapter's real path is what makes
        the "adapter's params -> PageRequest -> Page -> to_envelope()" round
        trip actually exercised, rather than trivially passing against a
        Page literal that was never produced by any real code.
"""

from typing import Any

from greentechhub_core.query.envelope import to_envelope, total_pages
from greentechhub_core.query.types import Page


class PageContract:
    """Inherit this class in a test module, defining `page` as a pytest
    fixture built from the adapter's real pagination path, to run the shared
    Page/envelope conformance suite.
    """

    def test_envelope_pages_matches_total_pages(self, page: Page[Any]) -> None:
        envelope = to_envelope(page)
        assert envelope["pages"] == total_pages(page.total, page.size)

    def test_envelope_carries_the_page_fields_through_unchanged(self, page: Page[Any]) -> None:
        envelope = to_envelope(page)
        assert envelope["items"] == page.items
        assert envelope["total"] == page.total
        assert envelope["page"] == page.page
        assert envelope["size"] == page.size
