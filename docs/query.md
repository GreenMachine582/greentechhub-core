[← Back to README](../README.md)

# 🔍 Query

```python
# greentechhub_core/query/types.py
@dataclass
class Filter:
    field: str
    operator: Operator          # eq, gt, lt, in, contains, ...
    value: Any

@dataclass
class PageRequest:
    page: int
    size: int
    sort: list[Sort]
    filters: list[Filter]

@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
```

`greentechhub-core` defines these types and the response envelope shape only. It does not parse a FastAPI `Query(...)` or Django's `request.GET` — that translation, and the actual paging mechanism (`fastapi-pagination` vs. Django's `Paginator`), is adapter-layer. Both adapters produce the same `Page` envelope, so consumers render results identically regardless of which backend served the data.

## SQLAlchemy

With the `[sqlalchemy]` extra, `greentechhub_core.sqlalchemy` applies these types to a service's own select. Parsing the
request stays adapter-layer (greentechhub-fastapi's `parse_sort("name,-date")` gives the `Sort`s); the database work
doesn't depend on the framework.

```python
from greentechhub_core.query.types import Sort
from greentechhub_core.sqlalchemy import order_by, paginate

ALLOWED = {"name": Stock.name, "date": Stock.created, "id": Stock.id}   # what clients may sort on
sorts = [Sort(field="date", direction="desc")]                          # e.g. parse_sort("-date")

stmt = select(Stock).where(Stock.active)
stmt = stmt.order_by(*order_by(sorts, ALLOWED, default=[Sort(field="id")]))
items, total = await paginate(session, stmt, offset=(page - 1) * size, limit=size)
```

- `order_by(sorts, allowed, *, default=())` maps each `Sort` to `column.asc()` / `.desc()` through the allow-list. A
  field it doesn't list is skipped (a stale or hand-edited URL still renders); when nothing usable is left, `default`
  applies. Add a unique tie-breaker (such as `id`) so pages don't shuffle between requests.
- `paginate(session, stmt, *, offset, limit, scalars=True)` (an `AsyncSession`, SQLModel's included) and
  `paginate_sync` (a `Session`) return one page plus the total the statement matches. The count ignores the
  statement's order and any limit or offset already on it. `scalars=True` returns the entity of a `select(Model)`;
  pass `False` for rows of a multi-column select.
