import asyncio
from datetime import timedelta

from greentechhub_core.identity import (
    AuthentikIdentityProvider,
    DevelopmentIdentityProvider,
    Identity,
    RawAuthContext,
)

_SECRET = "test-secret-key"

# Realistic Authentik forward-auth headers, per Authentik's own documented
# proxy/forward-auth outpost header set.
_AUTHENTIK_HEADERS = {
    "X-authentik-username": "jdoe",
    "X-authentik-groups": "admins|users",
    "X-authentik-email": "jdoe@example.com",
    "X-authentik-uid": "9f0e2372-driver-uid",
    "X-authentik-name": "Jane Doe",
    "X-authentik-jwt": "eyJhbGciOiJIUzI1NiJ9.fake.signature",
}


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


# Authentik forward-auth


def test_authentik_maps_headers_to_identity():
    identity = AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=_AUTHENTIK_HEADERS))
    assert identity is not None
    assert identity.subject == "9f0e2372-driver-uid"
    assert identity.username == "jdoe"
    assert identity.email == "jdoe@example.com"
    assert identity.groups == ["admins", "users"]


def test_authentik_claims_capture_every_prefixed_header():
    identity = AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=_AUTHENTIK_HEADERS))
    assert identity.claims == {
        "username": "jdoe",
        "groups": "admins|users",
        "email": "jdoe@example.com",
        "uid": "9f0e2372-driver-uid",
        "name": "Jane Doe",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.fake.signature",
    }


def test_authentik_subject_falls_back_to_username_when_uid_absent():
    headers = {k: v for k, v in _AUTHENTIK_HEADERS.items() if k != "X-authentik-uid"}
    identity = AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=headers))
    assert identity.subject == "jdoe"


def test_authentik_missing_username_resolves_to_none():
    headers = {k: v for k, v in _AUTHENTIK_HEADERS.items() if k != "X-authentik-username"}
    assert AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=headers)) is None


def test_authentik_empty_headers_resolves_to_none_without_raising():
    assert AuthentikIdentityProvider().resolve_sync(RawAuthContext()) is None


def test_authentik_missing_groups_header_defaults_to_empty_list():
    headers = {k: v for k, v in _AUTHENTIK_HEADERS.items() if k != "X-authentik-groups"}
    identity = AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=headers))
    assert identity.groups == []


def test_authentik_header_lookup_is_case_insensitive():
    headers = {k.lower(): v for k, v in _AUTHENTIK_HEADERS.items()}
    identity = AuthentikIdentityProvider().resolve_sync(RawAuthContext(headers=headers))
    assert identity is not None
    assert identity.username == "jdoe"


def test_authentik_custom_header_prefix_and_groups_separator():
    provider = AuthentikIdentityProvider(header_prefix="X-Custom-", groups_separator=",")
    headers = {
        "X-Custom-username": "bob",
        "X-Custom-groups": "team-a,team-b",
    }
    identity = provider.resolve_sync(RawAuthContext(headers=headers))
    assert identity is not None
    assert identity.username == "bob"
    assert identity.groups == ["team-a", "team-b"]


def test_authentik_require_headers_beyond_username():
    provider = AuthentikIdentityProvider(require_headers=("username", "email"))
    headers = {"X-authentik-username": "jdoe"}
    assert provider.resolve_sync(RawAuthContext(headers=headers)) is None


def test_authentik_resolve_and_resolve_sync_agree():
    provider = AuthentikIdentityProvider()
    raw = RawAuthContext(headers=_AUTHENTIK_HEADERS)
    assert asyncio.run(provider.resolve(raw)) == provider.resolve_sync(raw)
