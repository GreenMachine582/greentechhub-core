from greentechhub_core.security import DEFAULT_SECRET_KEYS, redact

# redact — unquoted values


def test_redacts_unquoted_password_value():
    assert redact("password=secret123") == "password=***REDACTED***"


def test_does_not_swallow_following_key_value_pair():
    result = redact("password=secret123 remember_me=true")
    assert result == "password=***REDACTED*** remember_me=true"


def test_case_insensitive_key_matching():
    assert redact("PASSWORD=secret123") == "PASSWORD=***REDACTED***"


# redact — quoted values


def test_redacts_double_quoted_value():
    assert redact('"token": "abc123"') == '"token": "***REDACTED***"'


def test_redacts_single_quoted_value():
    assert redact("token: 'abc123'") == "token: '***REDACTED***'"


# redact — authorization / auth-scheme handling


def test_redacts_bearer_token_leaving_scheme_word_intact():
    result = redact("Authorization: Bearer abc.def.ghi")
    assert result == "Authorization: Bearer ***REDACTED***"


# redact — no match


def test_line_with_no_matching_keys_passes_through_unchanged():
    text = "user=bob remember_me=true"
    assert redact(text) == text


def test_empty_string_passes_through_unchanged():
    assert redact("") == ""


# redact — extra_keys


def test_extra_keys_extends_default_set():
    text = "stripe_secret=sk_live_1234"
    assert redact(text) == text  # not redacted without extra_keys
    assert redact(text, extra_keys=["stripe_secret"]) == "stripe_secret=***REDACTED***"


def test_default_secret_keys_is_non_empty_and_lowercase():
    assert len(DEFAULT_SECRET_KEYS) > 0
    assert all(key == key.lower() for key in DEFAULT_SECRET_KEYS)


# redact — custom replacement


def test_custom_replacement_string():
    assert redact("token=abc123", replacement="[hidden]") == "token=[hidden]"


# redact — multiple secrets, mixed shapes, one line


def test_multiple_secrets_on_one_line_all_redacted():
    text = 'user=bob password=hunter2 token="abc123"'
    result = redact(text)
    assert result == 'user=bob password=***REDACTED*** token="***REDACTED***"'
