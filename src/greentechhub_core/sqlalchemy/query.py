"""Applying core's query types to a SQLAlchemy select: sorting through an
allow-list, and one page plus the total — see docs/query.md#sqlalchemy.

Framework-neutral like the rest of core: an adapter parses the request into
`Sort`s (greentechhub-fastapi's `parse_sort("name,-date")`, a gth-ui
TableState's sort and direction, ...) and the service applies them here to
its own statement.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from greentechhub_core.query.types import Sort


def order_by(
    sorts: Iterable[Sort],
    allowed: Mapping[str, Any],
    *,
    default: Iterable[Sort] = (),
) -> list[ColumnElement[Any]]:
    """`ORDER BY` clauses for `sorts`, in order, for `stmt.order_by(*...)`.

    `allowed` maps each public field name to its column (a mapped attribute
    or a Column), so a client can only sort on what the service exposes. A
    field it doesn't list is skipped rather than raised, so a stale or
    hand-edited URL still renders. When nothing in `sorts` is allowed,
    `default` (resolved the same way) is used instead; with no default,
    the result is empty and the database's order applies.
    """
    clauses = _resolve(sorts, allowed)
    return clauses or _resolve(default, allowed)


def _resolve(sorts: Iterable[Sort], allowed: Mapping[str, Any]) -> list[ColumnElement[Any]]:
    clauses = []
    for sort in sorts:
        column = allowed.get(sort.field)
        if column is not None:
            clauses.append(column.desc() if sort.direction == "desc" else column.asc())
    return clauses


def _count(stmt: Select[Any]) -> Select[Any]:
    # The total ignores the statement's order (pointless to sort a count) and
    # any limit/offset already on it.
    return select(func.count()).select_from(stmt.order_by(None).limit(None).offset(None).subquery())


async def paginate(
    session: AsyncSession,
    stmt: Select[Any],
    *,
    offset: int,
    limit: int,
    scalars: bool = True,
) -> tuple[Sequence[Any], int]:
    """One page of `stmt` and the total number of rows it matches.

    `scalars=True` (default) returns the first column of each row: the
    entity for a `select(Model)`, as an ORM page wants. Pass False for a
    multi-column select to get the rows. Works with SQLModel's AsyncSession,
    which subclasses SQLAlchemy's.
    """
    total = (await session.execute(_count(stmt))).scalar_one()
    result = await session.execute(stmt.offset(offset).limit(limit))
    return (result.scalars().all() if scalars else result.all()), total


def paginate_sync(
    session: Session,
    stmt: Select[Any],
    *,
    offset: int,
    limit: int,
    scalars: bool = True,
) -> tuple[Sequence[Any], int]:
    """paginate() for a sync Session."""
    total = session.execute(_count(stmt)).scalar_one()
    result = session.execute(stmt.offset(offset).limit(limit))
    return (result.scalars().all() if scalars else result.all()), total
