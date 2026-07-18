import dataclasses

import pytest

from greentechhub_core.identity import Identity, RawAuthContext

# Identity


def test_identity_construction_requires_keyword_args():
    Identity(subject="u1", username="alice", email="alice@example.com", groups=["dev"], claims={})
    with pytest.raises(TypeError):
        Identity("u1", "alice", "alice@example.com", ["dev"], {})


def test_identity_is_frozen():
    identity = Identity(subject="u1", username="alice", email=None, groups=[], claims={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.username = "bob"


def test_identity_email_may_be_none():
    identity = Identity(subject="u1", username="alice", email=None, groups=[], claims={})
    assert identity.email is None


def test_identity_groups_and_claims_round_trip():
    identity = Identity(
        subject="u1",
        username="alice",
        email="alice@example.com",
        groups=["homelab-users", "admin-users"],
        claims={"custom": "value"},
    )
    assert identity.groups == ["homelab-users", "admin-users"]
    assert identity.claims == {"custom": "value"}


# RawAuthContext


def test_raw_auth_context_defaults():
    raw = RawAuthContext()
    assert raw.token is None
    assert raw.headers == {}
    assert raw.dev_mode is False


def test_raw_auth_context_default_headers_are_independent_per_instance():
    # default_factory=dict -- two RawAuthContexts must not share one mutable dict.
    a = RawAuthContext()
    b = RawAuthContext()
    a.headers["X-Forwarded-User"] = "alice"
    assert b.headers == {}


def test_raw_auth_context_construction_requires_keyword_args():
    RawAuthContext(token="abc", headers={}, dev_mode=True)
    with pytest.raises(TypeError):
        RawAuthContext("abc", {}, True)


def test_raw_auth_context_is_frozen():
    raw = RawAuthContext()
    with pytest.raises(dataclasses.FrozenInstanceError):
        raw.dev_mode = True
