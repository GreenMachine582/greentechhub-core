"""Identity's display_name/email_verified/provider fields, and how each
provider fills them."""

from datetime import UTC, datetime, timedelta

import jwt

from greentechhub_core.identity import (
    AuthentikIdentityProvider,
    DevelopmentIdentityProvider,
    Identity,
    RawAuthContext,
)

SECRET = "test-secret"


def _identity(**overrides: object) -> Identity:
    fields: dict[str, object] = {
        "subject": "u-1",
        "username": "alice",
        "email": "alice@example.com",
        "groups": [],
        "claims": {},
    }
    fields.update(overrides)
    return Identity(**fields)  # type: ignore[arg-type]


def test_new_fields_default_for_existing_callers() -> None:
    identity = _identity()
    assert identity.display_name is None
    assert identity.email_verified is False
    assert identity.provider == "local"


def test_issued_token_round_trips_the_new_fields() -> None:
    provider = DevelopmentIdentityProvider(secret_key=SECRET)
    original = _identity(display_name="Alice A", email_verified=True, provider="oidc:authentik")
    resolved = provider.resolve_sync(RawAuthContext(token=provider.issue(original)))
    assert resolved == original


def test_token_issued_before_the_new_fields_still_resolves() -> None:
    now = datetime.now(UTC)
    old_payload = {
        "sub": "u-1",
        "username": "alice",
        "email": None,
        "groups": [],
        "claims": {},
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(old_payload, SECRET, algorithm="HS256")
    resolved = DevelopmentIdentityProvider(secret_key=SECRET).resolve_sync(
        RawAuthContext(token=token)
    )
    assert resolved is not None
    assert (resolved.display_name, resolved.email_verified, resolved.provider) == (
        None,
        False,
        "local",
    )


def test_dev_identity_is_tagged_dev() -> None:
    identity = DevelopmentIdentityProvider(secret_key=SECRET).resolve_sync(
        RawAuthContext(dev_mode=True)
    )
    assert identity is not None
    assert identity.provider == "dev"


def test_authentik_reads_name_and_vouches_for_email() -> None:
    identity = AuthentikIdentityProvider().resolve_sync(
        RawAuthContext(
            headers={
                "X-authentik-username": "alice",
                "X-authentik-uid": "abc123",
                "X-authentik-email": "alice@example.com",
                "X-authentik-name": "Alice Anderson",
            }
        )
    )
    assert identity is not None
    assert identity.display_name == "Alice Anderson"
    assert identity.email_verified is True
    assert identity.provider == "authentik"


def test_authentik_without_email_or_name() -> None:
    identity = AuthentikIdentityProvider().resolve_sync(
        RawAuthContext(headers={"X-authentik-username": "alice", "X-authentik-name": ""})
    )
    assert identity is not None
    assert identity.display_name is None
    assert identity.email_verified is False


def test_authentik_provider_name_is_configurable() -> None:
    identity = AuthentikIdentityProvider(provider="authentik-work").resolve_sync(
        RawAuthContext(headers={"X-authentik-username": "alice"})
    )
    assert identity is not None
    assert identity.provider == "authentik-work"
