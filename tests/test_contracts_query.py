"""Smoke-tests PageContract's own mechanics using a hand-built Page.

Acceptable here only because core has no adapter of its own to produce a
real one from an actual pagination path — see PageContract's docstring,
which requires a real adapter to build `page` from its own query-param
parsing rather than a literal like this.
"""

import pytest

from greentechhub_core.contracts.query import PageContract
from greentechhub_core.query import Page


class TestPageContract(PageContract):
    @pytest.fixture
    def page(self) -> Page[str]:
        return Page(items=["a", "b", "c"], total=25, page=2, size=10)
