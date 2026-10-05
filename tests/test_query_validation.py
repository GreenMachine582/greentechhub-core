from datetime import date

import pytest

from greentechhub_core.query import (
    OPERATORS_BY_TYPE,
    Filter,
    FilterField,
    FilterGroup,
    Operator,
    validate_filters,
)
from greentechhub_core.types import BadRequestError

FIELDS = [
    FilterField(key="name", type="text"),
    FilterField(key="units", type="number"),
    FilterField(key="traded", type="date"),
    FilterField(key="kind", type="choice", choices={"buy": "Buy", "sell": "Sell"}),
    FilterField(key="archived", type="bool"),
]


def _f(field, op, value):
    return Filter(field=field, operator=Operator(op), value=value)


def _problems(filters, fields=FIELDS, **limits):
    with pytest.raises(BadRequestError) as caught:
        validate_filters(filters, fields, **limits)
    assert caught.value.code == "invalid_filters"
    return caught.value.details


# ── FilterField ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("kwargs", "error"), [
    ({"type": "money"}, "type must be one of"),
    ({"type": "choice"}, "needs choices"),
    ({"type": "text", "choices": ["a"]}, "only a choice field"),
    ({"type": "text", "operators": []}, "can't be empty"),
])
def test_a_filter_field_checks_itself(kwargs, error):
    with pytest.raises(ValueError, match=error):
        FilterField(key="f", **kwargs)


def test_choices_in_any_shape_and_operator_overrides():
    for choices in ({"a": "A"}, [("a", "A")], ["a"]):
        assert FilterField(key="k", type="choice", choices=choices).choice_values == {"a"}
    narrowed = FilterField(key="n", type="number", operators=["eq", Operator.GT])
    assert narrowed.allowed_operators == {Operator.EQ, Operator.GT}
    assert FilterField(key="d", type="date").allowed_operators == OPERATORS_BY_TYPE["date"]


# ── values ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("clause", "expected"), [
    (_f("units", "gte", "12"), 12),
    (_f("units", "lt", "1.5"), 1.5),
    (_f("units", "eq", 3.0), 3),
    (_f("traded", "gt", "2026-01-31"), date(2026, 1, 31)),
    (_f("traded", "lt", date(2026, 2, 1)), date(2026, 2, 1)),
    (_f("archived", "eq", "true"), True),
    (_f("archived", "ne", False), False),
    (_f("kind", "eq", "buy"), "buy"),
    (_f("name", "contains", "BHP"), "BHP"),
    (_f("units", "is_null", True), True),
])
def test_values_are_normalised_to_the_fields_type(clause, expected):
    (result,) = validate_filters([clause], FIELDS)
    assert result.value == expected and type(result.value) is type(expected)


@pytest.mark.parametrize(("clause", "message"), [
    (_f("units", "eq", True), "'units' expects a number"),
    (_f("units", "eq", "lots"), "'units' expects a number"),
    (_f("units", "eq", "nan"), "'units' expects a number"),
    (_f("traded", "eq", "31/01/2026"), "'traded' expects a date (YYYY-MM-DD)"),
    (_f("archived", "eq", "yes"), "'archived' expects true or false"),
    (_f("kind", "eq", "hold"), "'kind' 'hold' isn't one of the choices"),
    (_f("name", "eq", 5), "'name' expects text"),
    (_f("name", "is_null", "true"), "'name' is_null expects true or false"),
    (_f("name", "eq", ["a"]), "'name' eq expects one value, not a list"),
])
def test_values_that_dont_fit_are_refused(clause, message):
    (problem,) = _problems([clause])
    assert problem == {"path": "0", "field": clause.field, "message": message}


@pytest.mark.parametrize(("clause", "message"), [
    (_f("units", "contains", "1"), "contains doesn't apply to 'units'"),
    (_f("kind", "gt", "buy"), "gt doesn't apply to 'kind'"),
    (_f("archived", "in", [True]), "in doesn't apply to 'archived'"),
    (_f("secret", "eq", "x"), "'secret' can't be filtered on"),
])
def test_unknown_fields_and_operators_a_type_doesnt_take_are_refused(clause, message):
    assert _problems([clause])[0]["message"] == message


def test_lists_for_in_and_not_in():
    (result,) = validate_filters([_f("units", "in", ["1", 2, "3.5"])], FIELDS)
    assert result.value == [1, 2, 3.5]
    assert _problems([_f("kind", "in", [])])[0]["message"] == "'kind' in expects a non-empty list"
    assert _problems([_f("kind", "not_in", "buy")])[0]["message"] == (
        "'kind' not_in expects a non-empty list")
    assert _problems([_f("kind", "in", ["buy", "hold"])])[0]["message"] == (
        "'kind' 'hold' isn't one of the choices")
    assert _problems([_f("units", "in", list(range(4)))], max_values=3)[0]["message"] == (
        "'units' in takes at most 3 values")


# ── trees ──────────────────────────────────────────────────────────────────


def test_a_nested_tree_is_normalised_with_its_modes():
    tree = [
        _f("kind", "eq", "buy"),
        FilterGroup(mode="or", filters=(
            _f("units", "gt", "100"),
            FilterGroup(filters=(_f("archived", "eq", "false"),)),
        )),
    ]
    first, group = validate_filters(tree, {f.key: f for f in FIELDS})
    assert first == _f("kind", "eq", "buy")
    assert group.mode == "or"
    assert group.filters[0].value == 100
    assert group.filters[1] == FilterGroup(filters=(_f("archived", "eq", False),))


def test_depth_and_count_limits():
    deep = FilterGroup(filters=(FilterGroup(filters=(FilterGroup(filters=(
        _f("name", "eq", "x"),)),)),))
    assert _problems([deep], max_depth=2) == [
        {"path": "0.0.0", "field": None, "message": "groups nest at most 2 deep"}]
    assert validate_filters([deep], FIELDS, max_depth=3) == [deep]
    many = [_f("name", "eq", str(i)) for i in range(4)]
    assert _problems(many, max_filters=3) == [
        {"path": "3", "field": "name", "message": "at most 3 filters"}]


def test_every_problem_is_collected_with_its_path():
    tree = [
        _f("units", "eq", "x"),
        FilterGroup(mode="or", filters=(
            _f("name", "eq", "ok"), _f("nope", "eq", 1), _f("kind", "eq", "hold"))),
    ]
    with pytest.raises(BadRequestError) as caught:
        validate_filters(tree, FIELDS)
    assert [(p["path"], p["field"]) for p in caught.value.details] == [
        ("0", "units"), ("1.1", "nope"), ("1.2", "kind")]
    assert str(caught.value) == "'units' expects a number (and 2 more)"


def test_the_result_feeds_sqlalchemy_where():
    sa = pytest.importorskip("sqlalchemy")
    from greentechhub_core.sqlalchemy import where

    metadata = sa.MetaData()
    trades = sa.Table("trades", metadata, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("units", sa.Integer), sa.Column("traded", sa.Date))
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(trades.insert(), [
            {"id": 1, "units": 5, "traded": date(2026, 1, 1)},
            {"id": 2, "units": 50, "traded": date(2026, 3, 1)},
        ])
        filters = validate_filters(
            [_f("units", "gte", "10"), _f("traded", "gt", "2026-02-01")], FIELDS)
        condition = where(filters, {"units": trades.c.units, "traded": trades.c.traded})
        ids = conn.execute(sa.select(trades.c.id).where(condition)).scalars().all()
    assert ids == [2]
