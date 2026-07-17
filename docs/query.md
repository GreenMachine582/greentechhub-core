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
