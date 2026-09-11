"""contracts.identity — IdentityProviderContract: a reusable pytest test class
any IdentityProvider implementation (this package's own
DevelopmentIdentityProvider, a future AuthentikIdentityProvider, or an
adapter's own IdentityProvider) can inherit to get baseline conformance
coverage for free — see docs/testing.md.

A concrete subclass supplies two fixtures these test methods consume by name
(pytest's fixture-injection-by-parameter-name mechanism, not an abstract
method a subclass overrides):
    provider: a constructed IdentityProvider instance under test.
    valid_raw_context: a RawAuthContext this provider resolves to a real,
        non-None Identity — the "happy path" input a subclass's own setup
        can actually satisfy (e.g. RawAuthContext(dev_mode=True) for
        DevelopmentIdentityProvider; a valid forward-auth header set for a
        future AuthentikIdentityProvider).

RawAuthContext() with no arguments is always a valid "nothing supplied"
empty context — every field on it defaults (see identity/models.py) — so
these tests construct one directly rather than requiring a third fixture.
"""

import asyncio
import dataclasses

import pytest

from greentechhub_core.identity.models import Identity, RawAuthContext
from greentechhub_core.identity.provider import IdentityProvider


class IdentityProviderContract:
    """Inherit this class in a test module, defining `provider` and
    `valid_raw_context` as pytest fixtures, to run the shared IdentityProvider
    conformance suite against a concrete implementation.
    """

    def test_resolve_and_resolve_sync_agree_for_a_valid_context(
        self, provider: IdentityProvider, valid_raw_context: RawAuthContext
    ) -> None:
        assert asyncio.run(provider.resolve(valid_raw_context)) == provider.resolve_sync(
            valid_raw_context
        )

    def test_resolve_and_resolve_sync_agree_for_an_empty_context(
        self, provider: IdentityProvider
    ) -> None:
        empty = RawAuthContext()
        assert asyncio.run(provider.resolve(empty)) == provider.resolve_sync(empty)

    def test_empty_context_resolves_to_none_without_raising(
        self, provider: IdentityProvider
    ) -> None:
        assert provider.resolve_sync(RawAuthContext()) is None

    def test_garbage_token_resolves_to_none_without_raising(
        self, provider: IdentityProvider
    ) -> None:
        assert provider.resolve_sync(RawAuthContext(token="not-a-real-token")) is None

    def test_valid_context_resolves_to_a_populated_identity(
        self, provider: IdentityProvider, valid_raw_context: RawAuthContext
    ) -> None:
        identity = provider.resolve_sync(valid_raw_context)
        assert isinstance(identity, Identity)
        assert identity.subject
        assert identity.username

    def test_resolved_identity_is_frozen(
        self, provider: IdentityProvider, valid_raw_context: RawAuthContext
    ) -> None:
        identity = provider.resolve_sync(valid_raw_context)
        assert identity is not None
        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.subject = "someone-else"
