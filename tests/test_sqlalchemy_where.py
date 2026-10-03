import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from greentechhub_core.query.types import Filter, FilterGroup, Operator
from greentechhub_core.sqlalchemy import where


class Base(DeclarativeBase):
    pass


class Part(Base):
    __tablename__ = "parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    category: Mapped[str]
    stock: Mapped[int]
    note: Mapped[str | None]


ALLOWED = {"name": Part.name, "category": Part.category, "stock": Part.stock, "note": Part.note}
ROWS = [
    {"id": 1, "name": "Alpha bolt", "category": "Sensor", "stock": 0, "note": None},
    {"id": 2, "name": "Bravo nut", "category": "Motor", "stock": 5, "note": "50% off"},
    {"id": 3, "name": "Charlie gear", "category": "Sensor", "stock": 12, "note": "a_b"},
    {"id": 4, "name": "Delta BOLT", "category": "Cable", "stock": 7, "note": "axb"},
]


@pytest.fixture
def session(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.insert(Part), ROWS)
    with sessionmaker(engine)() as s:
        yield s
    engine.dispose()


def F(field, op, value):  # noqa: N802 - reads like the type it builds
    return Filter(field=field, operator=Operator(op), value=value)


def ids(session, *filters) -> list[int]:
    stmt = sa.select(Part.id).order_by(Part.id)
    if (condition := where(filters, ALLOWED)) is not None:
        stmt = stmt.where(condition)
    return list(session.scalars(stmt))


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [
        ("eq", 5, [2]),
        ("ne", 5, [1, 3, 4]),
        ("gt", 5, [3, 4]),
        ("gte", 5, [2, 3, 4]),
        ("lt", 5, [1]),
        ("lte", 5, [1, 2]),
        ("in", [0, 7], [1, 4]),
        ("in", 12, [3]),  # a single value is wrapped
        ("not_in", [0, 7], [2, 3]),
    ],
)
def test_comparison_operators(session, op, value, expected):
    assert ids(session, F("stock", op, value)) == expected


def test_text_matching_is_case_insensitive(session):
    assert ids(session, F("name", "contains", "bolt")) == [1, 4]
    assert ids(session, F("name", "starts_with", "charLIE")) == [3]
    assert ids(session, F("name", "ends_with", "NUT")) == [2]


def test_wildcards_in_the_value_match_literally(session):
    assert ids(session, F("note", "contains", "50%")) == [2]
    assert ids(session, F("note", "contains", "%")) == [2]
    assert ids(session, F("note", "contains", "a_b")) == [3]  # not "axb"
    assert ids(session, F("note", "contains", "_")) == [3]


def test_is_null_takes_a_bool(session):
    assert ids(session, F("note", "is_null", True)) == [1]
    assert ids(session, F("note", "is_null", False)) == [2, 3, 4]


def test_top_level_filters_are_anded(session):
    assert ids(session, F("category", "eq", "Sensor"), F("stock", "gt", 0)) == [3]


def test_or_group_and_nested_groups(session):
    any_of = FilterGroup(mode="or", filters=(F("stock", "eq", 0), F("name", "contains", "gear")))
    assert ids(session, any_of) == [1, 3]
    # category in [Sensor, Cable] AND (stock = 0 OR name contains "bolt")
    nested = FilterGroup(filters=(
        F("category", "in", ["Sensor", "Cable"]),
        FilterGroup(mode="or", filters=(F("stock", "eq", 0), F("name", "contains", "bolt"))),
    ))
    assert ids(session, nested) == [1, 4]


def test_fields_not_allowed_are_skipped(session):
    assert ids(session, F("id", "eq", 1), F("stock", "eq", 5)) == [2]  # id isn't in ALLOWED
    assert where([F("password", "eq", "x")], ALLOWED) is None
    assert where([FilterGroup(mode="or", filters=(F("secret", "eq", 1),))], ALLOWED) is None


def test_nothing_to_apply_is_none(session):
    assert where([], ALLOWED) is None
    assert where([FilterGroup()], ALLOWED) is None  # an empty group restricts nothing
    assert ids(session, FilterGroup()) == [1, 2, 3, 4]


def test_operator_given_as_its_string_value(session):
    # Operator is a StrEnum, so a Filter built from raw text still works.
    assert ids(session, Filter(field="stock", operator="gte", value=7)) == [3, 4]
