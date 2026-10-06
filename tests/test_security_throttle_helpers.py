"""throttle_keys, ThrottleStatus.retry_after_seconds and lockout_message: the
pieces every adapter's lockout answer is built from."""

from datetime import timedelta

from greentechhub_core.security import (
    ThrottleStatus,
    account_key,
    client_key,
    lockout_message,
    throttle_keys,
)


def test_throttle_keys_count_the_account_and_a_known_client():
    assert throttle_keys(" Alice", "203.0.113.7") == [account_key("alice"),
                                                      client_key("203.0.113.7")]


def test_throttle_keys_without_an_address_count_the_account_only():
    assert throttle_keys("alice", None) == [account_key("alice")]
    assert throttle_keys("alice", "") == [account_key("alice")]


def _locked(retry_after: timedelta) -> ThrottleStatus:
    return ThrottleStatus(allowed=False, retry_after=retry_after)


def test_retry_after_seconds_rounds_up_to_whole_seconds():
    assert _locked(timedelta(seconds=89.2)).retry_after_seconds == 90
    assert _locked(timedelta(minutes=15)).retry_after_seconds == 900


def test_retry_after_seconds_is_at_least_one():
    assert _locked(timedelta(0)).retry_after_seconds == 1


def test_retry_after_seconds_is_none_when_allowed():
    assert ThrottleStatus(allowed=True).retry_after_seconds is None


def test_lockout_message_rounds_up_to_minutes():
    assert lockout_message("failed sign-ins", timedelta(minutes=15)) == (
        "Too many failed sign-ins. Try again in 15 minutes.")
    assert lockout_message("failed sign-ins", timedelta(minutes=14, seconds=1)) == (
        "Too many failed sign-ins. Try again in 15 minutes.")


def test_lockout_message_says_one_minute_in_the_singular():
    assert lockout_message("requests", timedelta(seconds=30)) == (
        "Too many requests. Try again in 1 minute.")
