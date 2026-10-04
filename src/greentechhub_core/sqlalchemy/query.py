"""Applying core's query types to a SQLAlchemy select: filtering and sorting
through an allow-list, and one page plus the total — see
docs/query.md#sqlalchemy.

Framework-neutral like the rest of core: an adapter parses the request into
`Sort`s (greentechhub-fastapi's `parse_sort("name,-date")`, a gth-ui
TableState's sort and direction, ...) and the service applies them here to
its own statement.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from greentechhub_core.query.types import Filter, FilterGroup, Operator, Page, PageRequest, Sort


def where(
    filters: Iterable[Filter | FilterGroup], allowed: Mapping[str, Any]
) -> ColumnElement[bool] | None:
    """One boolean condition for `filters` (AND-ed, as PageRequest.filters
    is), for `stmt.where(...)` — or None when nothing applies.

    `allowed` maps each public field name to its column, as for order_by, so
    a client can only filter on what the service exposes. A field it doesn't
    list is skipped rather than raised; a group whose clauses are all
    skipped (or that is empty) is skipped too.

    contains / starts_with / ends_with are case-insensitive and match `%`,
    `_` and `\\` literally. in / not_in take a list (a single value is
    wrapped); is_null takes a bool (False means IS NOT NULL). Values are
    compared as given: converting query-string text to the column's type is
    the caller's job.
    """
    return _combine("and", filters, allowed)


def _combine(
    mode: str, clauses: Iterable[Filter | FilterGroup], allowed: Mapping[str, Any]
) -> ColumnElement[bool] | None:
    parts = [p for c in clauses if (p := _clause(c, allowed)) is not None]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return (or_ if mode == "or" else and_)(*parts)


def _clause(clause: Filter | FilterGroup, allowed: Mapping[str, Any]) -> ColumnElement[bool] | None:
    if isinstance(clause, FilterGroup):
        return _combine(clause.mode, clause.filters, allowed)
    column = allowed.get(clause.field)
    if column is None:
        return None
    return _compare(column, Operator(clause.operator), clause.value)


def _like(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compare(column: Any, op: Operator, value: Any) -> ColumnElement[bool]:
    match op:
        case Operator.EQ:
            return column == value
        case Operator.NE:
            return column != value
        case Operator.GT:
            return column > value
        case Operator.GTE:
            return column >= value
        case Operator.LT:
            return column < value
        case Operator.LTE:
            return column <= value
        case Operator.IN | Operator.NOT_IN:
            values = list(value) if isinstance(value, (list, tuple, set, frozenset)) else [value]
            return column.in_(values) if op is Operator.IN else column.not_in(values)
        case Operator.CONTAINS:
            return column.ilike(f"%{_like(value)}%", escape="\\")
        case Operator.STARTS_WITH:
            return column.ilike(f"{_like(value)}%", escape="\\")
        case Operator.ENDS_WITH:
            return column.ilike(f"%{_like(value)}", escape="\\")
        case Operator.IS_NULL:
            return column.is_(None) if value else column.is_not(None)
    raise ValueError(f"unsupported operator {op!r}")  # pragma: no cover - every Operator is matched


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


# SQLModel's sessions subclass SQLAlchemy's and override execute() only to
# add a DeprecationWarning steering callers to exec(), so going through the
# subclass would warn on every page. These call SQLAlchemy's own execute(),
# which SQLModel's override delegates to anyway: same result, no warning.
async def _execute(session: AsyncSession, stmt: Select[Any]) -> Any:
    return await AsyncSession.execute(session, stmt)


def _execute_sync(session: Session, stmt: Select[Any]) -> Any:
    return Session.execute(session, stmt)


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
    which subclasses SQLAlchemy's, without its execute() DeprecationWarning.
    """
    total = (await _execute(session, _count(stmt))).scalar_one()
    result = await _execute(session, stmt.offset(offset).limit(limit))
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
    total = _execute_sync(session, _count(stmt)).scalar_one()
    result = _execute_sync(session, stmt.offset(offset).limit(limit))
    return (result.scalars().all() if scalars else result.all()), total


def _page_stmt(
    stmt: Select[Any],
    request: PageRequest,
    allowed: Mapping[str, Any],
    default_sort: Iterable[Sort],
) -> tuple[Select[Any], int]:
    if (condition := where(request.filters, allowed)) is not None:
        stmt = stmt.where(condition)
    # Appended after any order already on stmt, so a service can pin a
    # leading order and still let the request sort within it.
    stmt = stmt.order_by(*order_by(request.sort, allowed, default=default_sort))
    return stmt, (max(request.page, 1) - 1) * request.size


async def page(
    session: AsyncSession,
    stmt: Select[Any],
    request: PageRequest,
    allowed: Mapping[str, Any],
    *,
    default_sort: Iterable[Sort] = (),
    scalars: bool = True,
) -> Page[Any]:
    """A PageRequest in, a Page out: the request's filters (where), then its
    sort (order_by, falling back to `default_sort`), then one page
    (paginate) — what an API list route returns, e.g. via to_envelope.

    `allowed` is the allow-list for both filtering and sorting. A service
    that needs different ones calls where / order_by / paginate itself.
    Bounding `request.size` is the adapter's job (page_params' max_size); a
    page below 1 is read as 1.
    """
    stmt, offset = _page_stmt(stmt, request, allowed, default_sort)
    items, total = await paginate(session, stmt, offset=offset, limit=request.size, scalars=scalars)
    return Page(items=list(items), total=total, page=request.page, size=request.size)


def page_sync(
    session: Session,
    stmt: Select[Any],
    request: PageRequest,
    allowed: Mapping[str, Any],
    *,
    default_sort: Iterable[Sort] = (),
    scalars: bool = True,
) -> Page[Any]:
    """page() for a sync Session."""
    stmt, offset = _page_stmt(stmt, request, allowed, default_sort)
    items, total = paginate_sync(session, stmt, offset=offset, limit=request.size, scalars=scalars)
    return Page(items=list(items), total=total, page=request.page, size=request.size)
