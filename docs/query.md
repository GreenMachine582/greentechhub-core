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
class FilterGroup:                # AND / OR of filters; groups nest
    mode: Literal["and", "or"]
    filters: tuple[Filter | FilterGroup, ...]

@dataclass
class PageRequest:
    page: int
    size: int
    sort: list[Sort]
    filters: list[Filter | FilterGroup]   # implicitly AND-ed

@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
```

`greentechhub-core` defines these types and the response envelope shape only. It does not parse a FastAPI `Query(...)` or Django's `request.GET` — that translation, and the actual paging mechanism (`fastapi-pagination` vs. Django's `Paginator`), is adapter-layer. Both adapters produce the same `Page` envelope, so consumers render results identically regardless of which backend served the data.

## Validating filters

A filter tree from a client (greentechhub-ui's query builder, parsed by an adapter) names fields, operators and values
of its own choosing. `validate_filters` checks it against the fields a page allows and returns a normalised copy, so
the database only sees sound input:

```python
from greentechhub_core.query import FilterField, validate_filters

FIELDS = [
    FilterField(key="name", type="text"),
    FilterField(key="units", type="number"),
    FilterField(key="traded", type="date"),
    FilterField(key="kind", type="choice", choices={"buy": "Buy", "sell": "Sell"}),
    FilterField(key="archived", type="bool"),
]

filters = validate_filters(request.filters, FIELDS)   # BadRequestError("invalid_filters") on any problem
if (condition := where(filters, ALLOWED)) is not None:   # or page(...) with a PageRequest of them
    stmt = stmt.where(condition)
```

Each field's type decides the operators it takes (`OPERATORS_BY_TYPE`; pass `operators=` to narrow them) and the
values that fit:

| Type | Operators | Values become |
|---|---|---|
| `text` | eq, ne, contains, starts_with, ends_with, in, not_in, is_null | `str` |
| `number` | eq, ne, gt, gte, lt, lte, in, not_in, is_null | `int`, or `float` when not whole; numeric text is converted, `True` isn't a number |
| `date` | eq, ne, gt, gte, lt, lte, is_null | `datetime.date`, from ISO text (`2026-01-31`) or a date |
| `choice` | eq, ne, in, not_in, is_null | one of the field's `choices` (value → label, pairs or bare values) |
| `bool` | eq, ne, is_null | `bool`, from `true`/`false` too |

- `in` / `not_in` take a non-empty list of at most `max_values` (100), each checked by the type. `is_null` takes a
  bool. Any other operator takes one value.
- Groups nest at most `max_depth` (3) deep, and the tree holds at most `max_filters` (20) filters.
- A field not listed is refused, unlike `where`, which skips it silently.
- Every problem is collected into one `BadRequestError` with `code="invalid_filters"`. Its `details` list
  `{"path", "field", "message"}` per problem; `path` is the clause's index, dotted through groups (`"1.0"`), so a
  query builder can mark the row.

Adapters wrap it: greentechhub-fastapi's query-builder validation runs it after `parse_filter_json`, and Django can call
it on its own parsed filters.

## SQLAlchemy

With the `[sqlalchemy]` extra, `greentechhub_core.sqlalchemy` applies these types to a service's own select. Parsing the
request stays adapter-layer (greentechhub-fastapi's `page_params` builds the `PageRequest`); the database work doesn't
depend on the framework.

The one-call path is `page()`: a `PageRequest` in, a `Page` out.

```python
from greentechhub_core.query import Sort, to_envelope
from greentechhub_core.sqlalchemy import page

ALLOWED = {"name": Stock.name, "date": Stock.created, "id": Stock.id}   # what clients may filter and sort on

result = await page(session, select(Stock).where(Stock.active), request, ALLOWED,
                    default_sort=[Sort(field="id")])
return to_envelope(result)   # {"items", "total", "page", "size", "pages"}
```

- `page(session, stmt, request, allowed, *, default_sort=(), scalars=True)` (an `AsyncSession`) and `page_sync` (a
  `Session`) apply the request's filters with `where`, its sort with `order_by` (after any order already on `stmt`,
  falling back to `default_sort`), then one page with `paginate`. One `allowed` serves filtering and sorting; a page
  below 1 reads as 1, and bounding `size` is the adapter's job (`page_params`' `max_size`).

For anything else, such as separate filter and sort lists, use the three pieces it's built from:

```python
from greentechhub_core.query.types import Filter, FilterGroup, Operator, Sort
from greentechhub_core.sqlalchemy import order_by, paginate, where

ALLOWED = {"name": Stock.name, "date": Stock.created, "id": Stock.id}   # what clients may sort/filter on
sorts = [Sort(field="date", direction="desc")]                          # e.g. parse_sort("-date")
filters = [                                                             # e.g. parse_filters(...)
    Filter(field="category", operator=Operator.IN, value=["Sensor", "Cable"]),
    FilterGroup(mode="or", filters=(
        Filter(field="stock", operator=Operator.EQ, value=0),
        Filter(field="name", operator=Operator.CONTAINS, value="bolt"),
    )),
]

stmt = select(Stock).where(Stock.active)
if (condition := where(filters, ALLOWED)) is not None:
    stmt = stmt.where(condition)
stmt = stmt.order_by(*order_by(sorts, ALLOWED, default=[Sort(field="id")]))
items, total = await paginate(session, stmt, offset=(page - 1) * size, limit=size)
```

- `where(filters, allowed)` turns `Filter`s and `FilterGroup`s (top level AND-ed) into one condition, or `None` when
  nothing applies. Through the same kind of allow-list: a field it doesn't list is skipped, and so is a group left
  empty. The operators:

  | Operator | SQL |
  |---|---|
  | `eq` / `ne` / `gt` / `gte` / `lt` / `lte` | `=` `!=` `>` `>=` `<` `<=` |
  | `in` / `not_in` | `IN` / `NOT IN` — a list; a single value is wrapped |
  | `contains` / `starts_with` / `ends_with` | case-insensitive `ILIKE`, with `%`, `_` and `\` in the value matched literally |
  | `is_null` | `IS NULL` for `True`, `IS NOT NULL` for `False` |

  Values are compared as given. Converting query-string text (`"5"`) to the column's type is the caller's job.
- `order_by(sorts, allowed, *, default=())` maps each `Sort` to `column.asc()` / `.desc()` through the allow-list. A
  field it doesn't list is skipped (a stale or hand-edited URL still renders); when nothing usable is left, `default`
  applies. Add a unique tie-breaker (such as `id`) so pages don't shuffle between requests.
- `paginate(session, stmt, *, offset, limit, scalars=True)` (an `AsyncSession`, SQLModel's included) and
  `paginate_sync` (a `Session`) return one page plus the total the statement matches. The count ignores the
  statement's order and any limit or offset already on it. `scalars=True` returns the entity of a `select(Model)`;
  pass `False` for rows of a multi-column select.
