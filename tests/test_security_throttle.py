import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.security import (
    InMemoryAttemptStore,
    LoginThrottle,
    ThrottleStatus,
    account_key,
    client_key,
)

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def throttle(clock) -> LoginThrottle:
    return LoginThrottle(InMemoryAttemptStore(), max_failures=3, window=timedelta(minutes=10),
                         lockout=timedelta(minutes=5), clock=clock)


ALICE, IP = account_key("alice"), client_key("203.0.113.7")


def test_allowed_below_the_limit(throttle):
    assert throttle.check_sync(ALICE) == ThrottleStatus(allowed=True, failures=0)
    throttle.record_failure_sync(ALICE)
    status = throttle.record_failure_sync(ALICE)
    assert status == ThrottleStatus(allowed=True, failures=2)
    assert throttle.check_sync(ALICE).allowed


def test_the_failure_that_reaches_the_limit_locks(throttle, clock):
    for _ in range(2):
        throttle.record_failure_sync(ALICE)
    status = throttle.record_failure_sync(ALICE)
    assert status == ThrottleStatus(allowed=False, retry_after=timedelta(minutes=5), failures=3)
    clock.advance(minutes=2)
    assert throttle.check_sync(ALICE).retry_after == timedelta(minutes=3)


def test_the_lock_ends_and_one_more_failure_in_the_window_relocks(throttle, clock):
    for _ in range(3):
        throttle.record_failure_sync(ALICE)
    clock.advance(minutes=5)
    assert throttle.check_sync(ALICE).allowed
    # Still the same window: one try per lockout.
    assert not throttle.record_failure_sync(ALICE).allowed


def test_a_new_window_starts_the_count_again(throttle, clock):
    for _ in range(2):
        throttle.record_failure_sync(ALICE)
    clock.advance(minutes=10)
    assert throttle.record_failure_sync(ALICE) == ThrottleStatus(allowed=True, failures=1)


def test_success_clears_only_the_keys_given(throttle):
    for _ in range(2):
        throttle.record_failure_sync(ALICE, IP)
    throttle.record_success_sync(ALICE)
    assert throttle.check_sync(ALICE).failures == 0
    assert throttle.check_sync(IP).failures == 2


def test_the_most_restrictive_key_wins(throttle, clock):
    for _ in range(3):
        throttle.record_failure_sync(IP)  # this client guessed three accounts
    clock.advance(minutes=1)
    status = throttle.check_sync(account_key("bob"), IP)
    assert not status.allowed and status.retry_after == timedelta(minutes=4)
    assert status.failures == 3


def test_keys_ignore_case_and_spacing():
    assert account_key("  Alice ") == account_key("alice") == "account:alice"
    assert client_key(" 10.0.0.1 ") == "client:10.0.0.1"


@pytest.mark.parametrize("kwargs", [{"max_failures": 0}, {"window": timedelta(0)},
                                    {"lockout": timedelta(seconds=-1)}])
def test_rejects_bad_settings(kwargs):
    with pytest.raises(ValueError):
        LoginThrottle(InMemoryAttemptStore(), **kwargs)


def test_prune_drops_records_older_than_window_and_lockout(throttle, clock):
    throttle.record_failure_sync(ALICE)
    clock.advance(minutes=11)
    throttle.record_failure_sync(IP)
    assert throttle.prune_sync() == 1
    assert throttle.check_sync(ALICE).failures == 0
    assert throttle.check_sync(IP).failures == 1


def test_naive_clock_times_count_as_utc():
    naive = LoginThrottle(InMemoryAttemptStore(), max_failures=1,
                          clock=lambda: datetime(2026, 1, 1, 9, 0))
    assert not naive.record_failure_sync(ALICE).allowed
    assert not naive.check_sync(ALICE).allowed


def test_async_and_sync_agree(clock):
    sync = LoginThrottle(InMemoryAttemptStore(), max_failures=2, clock=clock)
    async_ = LoginThrottle(InMemoryAttemptStore(), max_failures=2, clock=clock)

    async def run():
        results = [await async_.record_failure(ALICE, IP) for _ in range(2)]
        results.append(await async_.check(ALICE))
        await async_.record_success(ALICE)
        results.append(await async_.check(ALICE, IP))
        results.append(await async_.prune())
        return results

    expected = [sync.record_failure_sync(ALICE, IP) for _ in range(2)]
    expected.append(sync.check_sync(ALICE))
    sync.record_success_sync(ALICE)
    expected.append(sync.check_sync(ALICE, IP))
    expected.append(sync.prune_sync())
    assert asyncio.run(run()) == expected
