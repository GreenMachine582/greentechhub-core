import pytest

from greentechhub_core.security import hash_password, verify_password

# hash_password


def test_hash_password_returns_str():
    hashed = hash_password("correct horse battery staple")
    assert isinstance(hashed, str)


def test_hashing_same_password_twice_produces_different_hashes():
    # bcrypt embeds a fresh random salt per call.
    a = hash_password("correct horse battery staple")
    b = hash_password("correct horse battery staple")
    assert a != b


def test_custom_rounds_is_respected():
    hashed = hash_password("correct horse battery staple", rounds=4)
    assert hashed.startswith("$2b$04$")


def test_invalid_rounds_raises():
    with pytest.raises(ValueError):
        hash_password("correct horse battery staple", rounds=1)


# verify_password


def test_correct_password_verifies():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_wrong_password_fails_verification():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_malformed_hash_returns_false_not_raise():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_empty_hash_returns_false_not_raise():
    assert verify_password("anything", "") is False
