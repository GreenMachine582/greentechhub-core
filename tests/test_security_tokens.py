from greentechhub_core.security import constant_time_compare, generate_token

# generate_token


def test_default_token_is_reasonably_long_and_url_safe():
    token = generate_token()
    assert len(token) >= 40
    assert all(c.isalnum() or c in "-_" for c in token)


def test_custom_num_bytes_changes_length():
    short = generate_token(num_bytes=8)
    long_ = generate_token(num_bytes=64)
    assert len(short) < len(long_)


def test_successive_calls_are_not_deterministic():
    assert generate_token() != generate_token()


# constant_time_compare


def test_equal_strings_compare_true():
    assert constant_time_compare("same-token", "same-token") is True


def test_different_strings_compare_false():
    assert constant_time_compare("token-a", "token-b") is False


def test_different_length_strings_compare_false():
    assert constant_time_compare("short", "a-much-longer-value") is False


def test_non_ascii_strings_do_not_raise():
    assert constant_time_compare("pässwörd", "pässwörd") is True
    assert constant_time_compare("pässwörd", "different") is False
