import asyncio
from datetime import timedelta

from greentechhub_core.identity import DevelopmentIdentityProvider, Identity, RawAuthContext

_SECRET = "test-secret-key"


def _provider(secret: str = _SECRET) -> DevelopmentIdentityProvider:
    return DevelopmentIdentityProvider(secret_key=secret)


def _sample_identity() -> Identity:
    return Identity(
        subject="u1",
        username="alice",
        email="alice@example.com",
        groups=["homelab-users"],
        claims={"custom": "value"},
    )


# dev mode


def test_dev_mode_returns_dummy_identity():
    identity = _provider().resolve_sync(RawAuthContext(dev_mode=True))
    assert identity is not None
    assert identity.subject == "dev-user"
    assert identity.username == "dev"
    assert identity.email == "dev@localhost"
    assert identity.groups == ["dev"]
    assert identity.claims == {"is_dev": True}


def test_dev_mode_returns_independent_identity_each_call():
    provider = _provider()
    a = provider.resolve_sync(RawAuthContext(dev_mode=True))
    b = provider.resolve_sync(RawAuthContext(dev_mode=True))
    a.groups.append("extra")
    assert b.groups == ["dev"]


def test_dev_mode_takes_precedence_over_a_present_token():
    provider = _provider()
    token = provider.issue(_sample_identity())
    identity = provider.resolve_sync(RawAuthContext(token=token, dev_mode=True))
    assert identity.subject == "dev-user"


# issue / resolve round trip


def test_issue_then_resolve_round_trips_to_the_same_identity():
    provider = _provider()
    original = _sample_identity()
    token = provider.issue(original)
    resolved = provider.resolve_sync(RawAuthContext(token=token))
    assert resolved == original


def test_resolve_and_resolve_sync_agree_for_a_valid_token():
    provider = _provider()
    raw = RawAuthContext(token=provider.issue(_sample_identity()))
    assert asyncio.run(provider.resolve(raw)) == provider.resolve_sync(raw)


def test_resolve_and_resolve_sync_agree_for_dev_mode():
    provider = _provider()
    raw = RawAuthContext(dev_mode=True)
    assert asyncio.run(provider.resolve(raw)) == provider.resolve_sync(raw)


def test_resolve_and_resolve_sync_agree_for_neither_present():
    provider = _provider()
    raw = RawAuthContext()
    assert asyncio.run(provider.resolve(raw)) is None
    assert provider.resolve_sync(raw) is None


# invalid input degrades to None, never raises


def test_neither_token_nor_dev_mode_resolves_to_none():
    assert _provider().resolve_sync(RawAuthContext()) is None


def test_empty_token_string_is_treated_as_absent():
    assert _provider().resolve_sync(RawAuthContext(token="")) is None


def test_tampered_token_resolves_to_none():
    provider = _provider()
    token = provider.issue(_sample_identity())
    tampered = token[:10] + ("x" if token[10] != "x" else "y") + token[11:]
    assert provider.resolve_sync(RawAuthContext(token=tampered)) is None


def test_expired_token_resolves_to_none():
    provider = _provider()
    token = provider.issue(_sample_identity(), expires_in=timedelta(seconds=-1))
    assert provider.resolve_sync(RawAuthContext(token=token)) is None


def test_wrong_secret_resolves_to_none():
    issuer = _provider("secret-a")
    verifier = _provider("secret-b")
    token = issuer.issue(_sample_identity())
    assert verifier.resolve_sync(RawAuthContext(token=token)) is None


def test_malformed_token_string_resolves_to_none():
    assert _provider().resolve_sync(RawAuthContext(token="not-a-jwt-at-all")) is None
