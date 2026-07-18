import dataclasses

import pytest

from greentechhub_core.query import Filter, Operator, Page, PageRequest, Sort

# Operator


def test_operator_members_equal_their_raw_string_value():
    assert Operator.EQ == "eq"
    assert Operator.GTE == "gte"
    assert Operator.IS_NULL == "is_null"


def test_operator_constructs_from_raw_string_value():
    assert Operator("contains") is Operator.CONTAINS


# Filter


def test_filter_construction_requires_keyword_args():
    Filter(field="status", operator=Operator.EQ, value="active")
    with pytest.raises(TypeError):
        Filter("status", Operator.EQ, "active")


def test_filter_is_frozen():
    f = Filter(field="status", operator=Operator.EQ, value="active")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.value = "inactive"


# Sort


def test_sort_direction_defaults_to_asc():
    assert Sort(field="created_at").direction == "asc"


def test_sort_construction_requires_keyword_args():
    Sort(field="created_at", direction="desc")
    with pytest.raises(TypeError):
        Sort("created_at", "desc")


def test_sort_is_frozen():
    s = Sort(field="created_at")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.direction = "desc"


# PageRequest


def test_page_request_defaults():
    request = PageRequest()
    assert request.page == 1
    assert request.size == 20
    assert request.sort == []
    assert request.filters == []


def test_page_request_default_lists_are_independent_per_instance():
    # default_factory=list -- two PageRequests must not share one mutable list.
    a = PageRequest()
    b = PageRequest()
    a.sort.append(Sort(field="x"))
    assert b.sort == []


def test_page_request_construction_requires_keyword_args():
    PageRequest(page=2, size=10, sort=[], filters=[])
    with pytest.raises(TypeError):
        PageRequest(2, 10, [], [])


def test_page_request_is_frozen():
    request = PageRequest()
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.page = 2


# Page


def test_page_construction_requires_keyword_args():
    Page(items=[1, 2, 3], total=3, page=1, size=20)
    with pytest.raises(TypeError):
        Page([1, 2, 3], 3, 1, 20)


def test_page_is_frozen():
    page = Page(items=[1, 2, 3], total=3, page=1, size=20)
    with pytest.raises(dataclasses.FrozenInstanceError):
        page.total = 4


def test_page_is_usable_as_a_generic():
    page = Page[int](items=[1, 2, 3], total=3, page=1, size=20)
    assert page.items == [1, 2, 3]
