"""ROLE_BOOTSTRAP entries match an identity's username as well as its
subject, since a user account's subject is generated."""

from greentechhub_core.identity import Identity
from greentechhub_core.permissions import Permission, Role, RoleResolver

ADMIN = Role(name="admin", permissions={Permission("users.manage")})


def _identity(subject: str, username: str) -> Identity:
    return Identity(subject=subject, username=username, email=None, groups=[], claims={})


def test_bootstrap_matches_the_username():
    resolver = RoleResolver(roles=[ADMIN], bootstrap={"alice": ["admin"]})
    assert resolver.roles_for_sync(_identity("0f" * 16, "alice")) == {"admin"}
    assert resolver.roles_for_sync(_identity("0f" * 16, "bob")) == frozenset()


def test_bootstrap_still_matches_the_subject():
    resolver = RoleResolver(roles=[ADMIN], bootstrap={"0f" * 16: ["admin"]})
    assert resolver.roles_for_sync(_identity("0f" * 16, "alice")) == {"admin"}


def test_an_identity_without_a_username_matches_by_subject_only():
    class Bare:
        subject = "alice"
        groups: list[str] = []

    resolver = RoleResolver(roles=[ADMIN], bootstrap={"alice": ["admin"]})
    assert resolver.roles_for_sync(Bare()) == {"admin"}
