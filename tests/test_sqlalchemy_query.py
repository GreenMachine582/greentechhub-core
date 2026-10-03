import asyncio

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from greentechhub_core.query import to_envelope
from greentechhub_core.query.types import Filter, FilterGroup, Operator, PageRequest, Sort
from greentechhub_core.sqlalchemy import order_by, page, page_sync, paginate, paginate_sync


class Base(DeclarativeBase):
    pass


class Part(Base):
    __tablename__ = "parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    stock: Mapped[int]


ALLOWED = {"name": Part.name, "stock": Part.stock, "id": Part.id}
# 12 parts: names p01..p12, stock cycling 0, 1, 2.
ROWS = [{"id": i, "name": f"p{i:02d}", "stock": i % 3} for i in range(1, 13)]


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = sa.create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.insert(Part), ROWS)
    async_engine = create_async_engine(
        url.replace("sqlite", "sqlite+aiosqlite"), poolclass=NullPool
    )
    yield {"sync": sessionmaker(engine), "async": async_sessionmaker(async_engine)}
    engine.dispose()
    asyncio.run(async_engine.dispose())


def _sql(clauses) -> list[str]:
    return [str(c) for c in clauses]


# order_by


def test_order_by_maps_fields_and_directions_in_order():
    clauses = order_by([Sort(field="stock", direction="desc"), Sort(field="name")], ALLOWED)
    assert _sql(clauses) == ["parts.stock DESC", "parts.name ASC"]


def test_order_by_skips_fields_not_allowed():
    clauses = order_by([Sort(field="password"), Sort(field="name", direction="desc")], ALLOWED)
    assert _sql(clauses) == ["parts.name DESC"]


def test_order_by_falls_back_to_the_default_when_nothing_is_allowed():
    default = [Sort(field="id", direction="desc")]
    assert _sql(order_by([Sort(field="secret")], ALLOWED, default=default)) == ["parts.id DESC"]
    assert _sql(order_by([], ALLOWED, default=default)) == ["parts.id DESC"]
    # The default only applies when the request gave nothing usable.
    assert _sql(order_by([Sort(field="name")], ALLOWED, default=default)) == ["parts.name ASC"]


def test_order_by_without_sorts_or_default_is_empty():
    assert order_by([], ALLOWED) == []


# paginate / paginate_sync


def _stmt(*sorts: Sort):
    return sa.select(Part).order_by(*order_by(sorts, ALLOWED, default=[Sort(field="id")]))


def test_paginate_sync_returns_a_page_and_the_total(db):
    with db["sync"]() as session:
        items, total = paginate_sync(session, _stmt(Sort(field="name", direction="desc")),
                                     offset=2, limit=3)
    assert total == 12
    assert [p.name for p in items] == ["p10", "p09", "p08"]


def test_paginate_async_returns_a_page_and_the_total(db):
    async def run():
        async with db["async"]() as session:
            return await paginate(session, _stmt(), offset=10, limit=5)

    items, total = asyncio.run(run())
    assert total == 12
    assert [p.id for p in items] == [11, 12]  # the last, short page


def test_paginate_counts_the_filtered_rows_and_ignores_limits(db):
    stmt = _stmt().where(Part.stock == 0).limit(1)  # a limit already on it doesn't cap the total
    with db["sync"]() as session:
        items, total = paginate_sync(session, stmt, offset=0, limit=2)
    assert total == 4
    assert [p.id for p in items] == [3, 6]


def test_paginate_past_the_end_is_empty_with_the_total(db):
    with db["sync"]() as session:
        assert paginate_sync(session, _stmt(), offset=50, limit=10) == ([], 12)


def test_paginate_rows_for_a_multi_column_select(db):
    stmt = sa.select(Part.name, Part.stock).order_by(Part.id)
    with db["sync"]() as session:
        rows, total = paginate_sync(session, stmt, offset=0, limit=2, scalars=False)
    assert total == 12
    assert [tuple(r) for r in rows] == [("p01", 1), ("p02", 2)]


# page / page_sync: a PageRequest in, a Page out


def _request(**kwargs) -> PageRequest:
    return PageRequest(**{"page": 1, "size": 5, **kwargs})


def test_page_sync_applies_filters_sort_and_paging(db):
    request = _request(
        page=2, size=2,
        sort=[Sort(field="name", direction="desc")],
        filters=[Filter(field="stock", operator=Operator.NE, value=0)],  # drops p03, p06, p09, p12
    )
    with db["sync"]() as session:
        result = page_sync(session, sa.select(Part), request, ALLOWED)
    assert (result.total, result.page, result.size) == (8, 2, 2)
    assert [p.name for p in result.items] == ["p08", "p07"]  # desc: p11 p10 | p08 p07 | ...


def test_page_async_with_a_filter_group(db):
    either = FilterGroup(mode="or", filters=(
        Filter(field="stock", operator=Operator.EQ, value=0),
        Filter(field="name", operator=Operator.EQ, value="p01"),
    ))

    async def run():
        async with db["async"]() as session:
            return await page(session, sa.select(Part), _request(filters=[either]), ALLOWED,
                              default_sort=[Sort(field="id")])

    result = asyncio.run(run())
    assert result.total == 5 and [p.id for p in result.items] == [1, 3, 6, 9, 12]


def test_page_ignores_disallowed_fields_and_uses_the_default_sort(db):
    request = _request(sort=[Sort(field="secret")],
                       filters=[Filter(field="secret", operator=Operator.EQ, value=1)])
    with db["sync"]() as session:
        result = page_sync(session, sa.select(Part), request, ALLOWED,
                           default_sort=[Sort(field="id", direction="desc")])
    assert result.total == 12 and [p.id for p in result.items] == [12, 11, 10, 9, 8]


def test_page_past_the_end_and_page_zero(db):
    with db["sync"]() as session:
        past = page_sync(session, sa.select(Part), _request(page=9), ALLOWED)
        zero = page_sync(session, sa.select(Part), _request(page=0, size=3), ALLOWED,
                         default_sort=[Sort(field="id")])
    assert (past.items, past.total) == ([], 12)
    assert [p.id for p in zero.items] == [1, 2, 3]  # page 0 reads as page 1


def test_page_round_trips_through_the_envelope(db):
    with db["sync"]() as session:
        result = page_sync(session, sa.select(Part), _request(size=5), ALLOWED,
                           default_sort=[Sort(field="id")])
    envelope = to_envelope(result)
    assert (envelope["total"], envelope["pages"], len(envelope["items"])) == (12, 3, 5)
