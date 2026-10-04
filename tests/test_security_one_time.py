import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.security import InMemoryTokenStore, OneTimeTokens, token_hash

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
RESET, VERIFY = "password_reset", "email_verification"


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
def store() -> InMemoryTokenStore:
    return InMemoryTokenStore()


@pytest.fixture
def tokens(store, clock) -> OneTimeTokens:
    return OneTimeTokens(store, clock=clock)


def test_only_the_hash_is_stored(tokens, store):
    token = tokens.issue_sync("alice", RESET)
    assert len(token) >= 40
    record = store.get_sync(token_hash(token))
    assert record is not None and record.token_hash != token
    assert (record.subject, record.purpose) == ("alice", RESET)
    assert record.expires_at == T0 + timedelta(hours=1)
    assert store.get_sync(token) is None


def test_peek_does_not_use_it_and_redeem_works_once(tokens):
    token = tokens.issue_sync("alice", RESET)
    assert tokens.peek_sync(token, RESET) == "alice"
    assert tokens.peek_sync(token, RESET) == "alice"
    assert tokens.redeem_sync(token, RESET) == "alice"
    assert tokens.redeem_sync(token, RESET) is None
    assert tokens.peek_sync(token, RESET) is None


def test_a_wrong_purpose_is_refused_without_using_it(tokens):
    token = tokens.issue_sync("alice", RESET)
    assert tokens.redeem_sync(token, VERIFY) is None
    assert tokens.peek_sync(token, VERIFY) is None
    assert tokens.redeem_sync(token, RESET) == "alice"


def test_unknown_and_expired_tokens(tokens, clock):
    assert tokens.redeem_sync("not-a-token", RESET) is None
    token = tokens.issue_sync("alice", RESET)
    clock.advance(hours=1)
    assert tokens.peek_sync(token, RESET) is None
    assert tokens.redeem_sync(token, RESET) is None


def test_a_new_token_revokes_the_old_one_for_that_purpose_only(tokens):
    first = tokens.issue_sync("alice", RESET)
    verify = tokens.issue_sync("alice", VERIFY)
    bobs = tokens.issue_sync("bob", RESET)
    second = tokens.issue_sync("alice", RESET)
    assert tokens.redeem_sync(first, RESET) is None
    assert tokens.redeem_sync(second, RESET) == "alice"
    assert tokens.redeem_sync(verify, VERIFY) == "alice"
    assert tokens.redeem_sync(bobs, RESET) == "bob"


def test_a_per_token_lifetime(tokens, clock):
    token = tokens.issue_sync("alice", VERIFY, lifetime=timedelta(days=2))
    clock.advance(days=1)
    assert tokens.redeem_sync(token, VERIFY) == "alice"


@pytest.mark.parametrize(("subject", "purpose", "lifetime"), [
    ("", RESET, None), ("alice", "", None), ("alice", RESET, timedelta(0)),
])
def test_rejects_bad_input(tokens, subject, purpose, lifetime):
    with pytest.raises(ValueError):
        tokens.issue_sync(subject, purpose, lifetime=lifetime)


def test_rejects_a_bad_default_lifetime(store):
    with pytest.raises(ValueError):
        OneTimeTokens(store, lifetime=timedelta(seconds=-1))


def test_prune_drops_tokens_used_or_expired_over_a_day_ago(tokens, store, clock):
    used = tokens.issue_sync("alice", RESET)
    tokens.redeem_sync(used, RESET)
    live = tokens.issue_sync("bob", RESET, lifetime=timedelta(days=3))
    clock.advance(days=1, minutes=1)
    assert tokens.prune_sync() == 1
    assert store.get_sync(token_hash(used)) is None
    assert tokens.peek_sync(live, RESET) == "bob"


def test_naive_clock_times_count_as_utc(store):
    tokens = OneTimeTokens(store, clock=lambda: datetime(2026, 1, 1, 9, 0))
    token = tokens.issue_sync("alice", RESET)
    assert store.get_sync(token_hash(token)).created_at == T0
    assert tokens.redeem_sync(token, RESET) == "alice"


def test_async_and_sync_agree(clock):
    async_tokens = OneTimeTokens(InMemoryTokenStore(), clock=clock)

    async def run():
        token = await async_tokens.issue("alice", RESET)
        return [
            await async_tokens.peek(token, RESET),
            await async_tokens.redeem(token, VERIFY),
            await async_tokens.redeem(token, RESET),
            await async_tokens.redeem(token, RESET),
            await async_tokens.redeem("nope", RESET),
            await async_tokens.prune(),
        ]

    sync_tokens = OneTimeTokens(InMemoryTokenStore(), clock=clock)
    token = sync_tokens.issue_sync("alice", RESET)
    expected = [
        sync_tokens.peek_sync(token, RESET),
        sync_tokens.redeem_sync(token, VERIFY),
        sync_tokens.redeem_sync(token, RESET),
        sync_tokens.redeem_sync(token, RESET),
        sync_tokens.redeem_sync("nope", RESET),
        sync_tokens.prune_sync(),
    ]
    assert asyncio.run(run()) == expected == ["alice", None, "alice", None, None, 0]
