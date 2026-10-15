from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.security import ApiToken, InMemoryApiTokenStore, new_api_token, token_hash

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def test_new_api_token_stores_only_the_hash():
    token, plaintext = new_api_token("alice", "backup", ["a", "a", "b"], now=T0)
    assert len(plaintext) >= 40 and plaintext not in repr(token)
    assert token.token_hash == token_hash(plaintext)
    assert len(token.id) == 32 and token.scopes == frozenset({"a", "b"})


def test_new_api_token_treats_naive_datetimes_as_utc():
    token, _ = new_api_token("alice", "n", [], now=T0.replace(tzinfo=None),
                             expires_at=datetime(2026, 1, 2, 9, 0))
    assert token.created_at == T0 and token.expires_at == T0 + timedelta(days=1)


@pytest.mark.parametrize("owner,name", [("", "n"), ("alice", "")])
def test_new_api_token_needs_an_owner_and_a_name(owner, name):
    with pytest.raises(ValueError, match="owner and a name"):
        new_api_token(owner, name, [], now=T0)


def test_new_api_token_rejects_a_past_expiry():
    with pytest.raises(ValueError, match="future"):
        new_api_token("alice", "n", [], now=T0, expires_at=T0)


def test_active():
    token = ApiToken(id="0" * 32, owner="a", name="n", scopes=frozenset(), token_hash="h",
                     created_at=T0, expires_at=T0 + timedelta(hours=1))
    assert token.active(T0) and not token.active(T0 + timedelta(hours=1))
    assert ApiToken(id="0" * 32, owner="a", name="n", scopes=frozenset(), token_hash="h",
                    created_at=T0).active(T0 + timedelta(days=3650))


def test_in_memory_store_defaults_to_the_real_clock():
    store = InMemoryApiTokenStore()
    token, plaintext = store.create_sync("alice", "n", [])
    assert abs(datetime.now(UTC) - token.created_at) < timedelta(minutes=1)
    assert store.verify_sync(plaintext).last_used_at >= token.created_at
