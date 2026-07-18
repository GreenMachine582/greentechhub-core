from greentechhub_core.logging.context import get_request_id, reset_request_id, set_request_id


def test_get_request_id_defaults_to_none():
    assert get_request_id() is None


def test_set_request_id_makes_it_visible_to_get_request_id():
    token = set_request_id("req-abc")
    try:
        assert get_request_id() == "req-abc"
    finally:
        reset_request_id(token)


def test_reset_request_id_restores_previous_value():
    outer_token = set_request_id("outer")
    inner_token = set_request_id("inner")
    reset_request_id(inner_token)
    try:
        assert get_request_id() == "outer"
    finally:
        reset_request_id(outer_token)


def test_reset_request_id_clears_back_to_unset():
    token = set_request_id("req-abc")
    reset_request_id(token)
    assert get_request_id() is None
