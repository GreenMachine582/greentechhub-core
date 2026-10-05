"""validation — checks a Filter / FilterGroup tree from a client (e.g.
greentechhub-ui's query builder, parsed by an adapter) against the fields a
page allows: each field's type decides the operators it takes and the values
that fit. The result is a normalised copy (numbers as int/float, dates as
datetime.date, bools as bool), ready for sqlalchemy.where — see
docs/query.md#validating-filters.

Framework-free: an adapter parses the request and turns the
BadRequestError into a response.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from greentechhub_core.query.types import Filter, FilterGroup, Operator
from greentechhub_core.types.errors import BadRequestError

FIELD_TYPES = ("text", "number", "date", "choice", "bool")
"""The field types a FilterField can have: greentechhub-ui's query builder's."""

_O = Operator
OPERATORS_BY_TYPE: dict[str, frozenset[Operator]] = {
    "text": frozenset({_O.EQ, _O.NE, _O.CONTAINS, _O.STARTS_WITH, _O.ENDS_WITH, _O.IN,
                       _O.NOT_IN, _O.IS_NULL}),
    "number": frozenset({_O.EQ, _O.NE, _O.GT, _O.GTE, _O.LT, _O.LTE, _O.IN, _O.NOT_IN,
                         _O.IS_NULL}),
    "date": frozenset({_O.EQ, _O.NE, _O.GT, _O.GTE, _O.LT, _O.LTE, _O.IS_NULL}),
    "choice": frozenset({_O.EQ, _O.NE, _O.IN, _O.NOT_IN, _O.IS_NULL}),
    "bool": frozenset({_O.EQ, _O.NE, _O.IS_NULL}),
}
"""The operators each field type takes unless a FilterField narrows them."""

_LIST_OPERATORS = frozenset({Operator.IN, Operator.NOT_IN})


def _choice_values(choices: Mapping[str, str] | Iterable[Any]) -> frozenset[str]:
    if isinstance(choices, Mapping):
        return frozenset(str(value) for value in choices)
    values = set()
    for choice in choices:
        values.add(str(choice if isinstance(choice, str) else choice[0]))
    return frozenset(values)


@dataclass(frozen=True, slots=True, kw_only=True)
class FilterField:
    """A field a client may filter on.

    Fields:
        key: the field name filters use (and sqlalchemy.where's `allowed` maps).
        type: one of FIELD_TYPES.
        choices: a choice field's values: value → label, (value, label)
            pairs, or bare values. Required for "choice", refused otherwise.
        operators: the operators allowed, instead of the type's defaults
            (OPERATORS_BY_TYPE).

    ValueError for an unknown type, misplaced or missing choices, or an
    empty operator list.
    """

    key: str
    type: str
    choices: Mapping[str, str] | Iterable[Any] | None = None
    operators: Iterable[Operator] | None = None
    _choice_set: frozenset[str] = field(init=False, repr=False, compare=False)
    _operator_set: frozenset[Operator] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.type not in FIELD_TYPES:
            raise ValueError(f"filter field {self.key!r}: type must be one of {FIELD_TYPES}")
        if self.type == "choice":
            if not self.choices:
                raise ValueError(f"filter field {self.key!r}: a choice field needs choices")
            object.__setattr__(self, "_choice_set", _choice_values(self.choices))
        else:
            if self.choices is not None:
                raise ValueError(f"filter field {self.key!r}: only a choice field has choices")
            object.__setattr__(self, "_choice_set", frozenset())
        if self.operators is None:
            operators = OPERATORS_BY_TYPE[self.type]
        else:
            operators = frozenset(Operator(op) for op in self.operators)
            if not operators:
                raise ValueError(f"filter field {self.key!r}: operators can't be empty")
        object.__setattr__(self, "_operator_set", operators)

    @property
    def allowed_operators(self) -> frozenset[Operator]:
        return self._operator_set

    @property
    def choice_values(self) -> frozenset[str]:
        return self._choice_set


def _number(value: Any) -> int | float:
    if isinstance(value, bool):
        raise ValueError("expects a number")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            raise ValueError("expects a number") from None
    else:
        raise ValueError("expects a number")
    if not math.isfinite(number):
        raise ValueError("expects a number")
    return int(number) if number.is_integer() else number


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValueError("expects a date (YYYY-MM-DD)")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError("expects true or false")


def _scalar(spec: FilterField, value: Any) -> Any:
    if spec.type == "number":
        return _number(value)
    if spec.type == "date":
        return _date(value)
    if spec.type == "bool":
        return _bool(value)
    if not isinstance(value, str):
        raise ValueError("expects text")
    if spec.type == "choice" and value not in spec.choice_values:
        raise ValueError(f"{value!r} isn't one of the choices")
    return value


class _Walk:
    def __init__(self, fields: Mapping[str, FilterField], max_depth: int, max_filters: int,
                 max_values: int) -> None:
        self.fields = fields
        self.max_depth = max_depth
        self.max_filters = max_filters
        self.max_values = max_values
        self.count = 0
        self.problems: list[dict[str, Any]] = []

    def problem(self, path: str, field_name: str | None, message: str) -> None:
        self.problems.append({"path": path, "field": field_name, "message": message})

    def clause(self, node: Filter | FilterGroup, path: str, depth: int) -> Filter | FilterGroup:
        if isinstance(node, FilterGroup):
            if depth > self.max_depth:
                self.problem(path, None, f"groups nest at most {self.max_depth} deep")
                return node
            children = tuple(self.clause(child, f"{path}.{i}", depth + 1)
                             for i, child in enumerate(node.filters))
            return FilterGroup(mode=node.mode, filters=children)
        self.count += 1
        if self.count == self.max_filters + 1:
            self.problem(path, node.field, f"at most {self.max_filters} filters")
        return self.filter(node, path)

    def filter(self, node: Filter, path: str) -> Filter:
        spec = self.fields.get(node.field)
        if spec is None:
            self.problem(path, node.field, f"{node.field!r} can't be filtered on")
            return node
        operator = Operator(node.operator)
        if operator not in spec.allowed_operators:
            self.problem(path, node.field, f"{operator.value} doesn't apply to {node.field!r}")
            return node
        try:
            value = self.value(spec, operator, node.value)
        except ValueError as exc:
            self.problem(path, node.field, f"{node.field!r} {exc}")
            return node
        return Filter(field=node.field, operator=operator, value=value)

    def value(self, spec: FilterField, operator: Operator, value: Any) -> Any:
        if operator is Operator.IS_NULL:
            if not isinstance(value, bool):
                raise ValueError("is_null expects true or false")
            return value
        if operator in _LIST_OPERATORS:
            if not isinstance(value, list | tuple) or not value:
                raise ValueError(f"{operator.value} expects a non-empty list")
            if len(value) > self.max_values:
                raise ValueError(f"{operator.value} takes at most {self.max_values} values")
            return [_scalar(spec, item) for item in value]
        if isinstance(value, list | tuple):
            raise ValueError(f"{operator.value} expects one value, not a list")
        return _scalar(spec, value)


def validate_filters(
    filters: Iterable[Filter | FilterGroup],
    fields: Iterable[FilterField] | Mapping[str, FilterField],
    *,
    max_depth: int = 3,
    max_filters: int = 20,
    max_values: int = 100,
) -> list[Filter | FilterGroup]:
    """Check `filters` (AND-ed, as PageRequest.filters is) against `fields`
    and return a normalised copy.

    Every clause's field must be one of `fields`, its operator one the field
    allows, and its value fit the field's type: a number (numeric text is
    converted; True isn't a number), a date (ISO text or a date), true/false,
    text, or one of a choice field's values. in / not_in take a non-empty
    list of at most `max_values`; is_null takes a bool. Groups nest at most
    `max_depth` deep and the tree holds at most `max_filters` filters.

    Every problem is collected into one BadRequestError (code
    "invalid_filters") whose details list {"path", "field", "message"} per
    problem; `path` is the clause's index, dotted through groups ("1.0").
    """
    if isinstance(fields, Mapping):
        by_key = dict(fields)
    else:
        by_key = {spec.key: spec for spec in fields}
    walk = _Walk(by_key, max_depth, max_filters, max_values)
    result = [walk.clause(node, str(i), 1) for i, node in enumerate(filters)]
    if walk.problems:
        first = walk.problems[0]["message"]
        more = len(walk.problems) - 1
        message = first if not more else f"{first} (and {more} more)"
        raise BadRequestError(message, code="invalid_filters", details=walk.problems)
    return result
