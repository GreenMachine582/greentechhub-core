"""security.password_problem and email.email_looks_valid: the form checks
sign-up, password reset and Settings share."""

import pytest

from greentechhub_core.email import EMAIL_INVALID, email_looks_valid
from greentechhub_core.security import (
    PASSWORD_TOO_SHORT,
    PASSWORD_UNCHANGED,
    PASSWORDS_DIFFER,
    password_problem,
)


def test_a_good_new_password_has_no_problem():
    assert password_problem("long-enough", "long-enough") is None
    assert password_problem("long-enough", "long-enough", current="old-password") is None


def test_too_short_is_a_problem_with_the_new_password():
    assert password_problem("short", "short") == ("new", "Use at least 8 characters.")
    four = PASSWORD_TOO_SHORT.format(min_length=4)
    assert password_problem("abc", "abc", min_length=4) == ("new", four)


def test_the_same_as_the_current_one_is_a_problem():
    assert password_problem("same-password", "same-password", current="same-password") == (
        "new", PASSWORD_UNCHANGED)


def test_a_mismatch_is_a_problem_with_the_confirmation():
    assert password_problem("long-enough", "long-enouhg") == ("confirm", PASSWORDS_DIFFER)


def test_checks_run_in_order():
    # too short wins over a mismatch; unchanged wins over a mismatch
    assert password_problem("short", "other")[0] == "new"
    unchanged = password_problem("same-password", "x", current="same-password")
    assert unchanged == ("new", PASSWORD_UNCHANGED)


@pytest.mark.parametrize("address", ["name@example.com", "a@b", "first.last+tag@sub.example.org"])
def test_addresses_that_look_valid(address):
    assert email_looks_valid(address)


@pytest.mark.parametrize("address", [
    "", "name", "@example.com", "name@", "a@b@c", "name @example.com", "name@exa mple.com",
    "name@example.com\n",
])
def test_addresses_that_dont(address):
    assert not email_looks_valid(address)


def test_the_message():
    assert EMAIL_INVALID == "Enter an email address, like name@example.com."
