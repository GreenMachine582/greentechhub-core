from greentechhub_core.query import Page, to_envelope, total_pages

# total_pages


def test_total_pages_exact_division():
    assert total_pages(100, 20) == 5


def test_total_pages_remainder_rounds_up():
    assert total_pages(101, 20) == 6


def test_total_pages_zero_size_returns_zero():
    assert total_pages(100, 0) == 0


def test_total_pages_negative_size_returns_zero():
    assert total_pages(100, -5) == 0


# to_envelope


def test_to_envelope_shape_and_computed_pages():
    page = Page(items=["a", "b"], total=42, page=2, size=20)
    assert to_envelope(page) == {
        "items": ["a", "b"],
        "total": 42,
        "page": 2,
        "size": 20,
        "pages": 3,
    }


def test_to_envelope_items_pass_through_unchanged():
    items = [{"id": 1}, {"id": 2}]
    page = Page(items=items, total=2, page=1, size=20)
    assert to_envelope(page)["items"] is items
