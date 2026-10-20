"""users.model — UserAccount (a person's account in one service), LinkedIdentity
(an external sign-in tied to it), ProvisioningPolicy and the pure rules every
UserStore follows — see docs/users.md.

The account's `id` is the service's own key: 32 hex characters, generated
once and never changed. It is what every other gth store keys on (settings,
grants, audit actor, notifications, API tokens) and what a service's own
tables reference, so switching or adding a sign-in method never re-keys
anyone. `username` is only the login name, so it may change.

An external sign-in (Authentik forward-auth, OIDC later) is a LinkedIdentity
row keyed on (provider, external_subject) — the IdP's own immutable id, e.g.
Authentik's `uid`. One account can hold several links.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Literal

from greentechhub_core.identity.models import Identity
from greentechhub_core.security.throttle import aware

LOCAL_PROVIDER = "local"

MAX_USERNAME = 255
MAX_EMAIL = 320
MAX_DISPLAY_NAME = 255

UPDATABLE = frozenset(
    {"username", "email", "email_verified", "display_name", "active", "password_hash",
     "last_login_at"}
)
"""The fields `UserStore.update` accepts; id, auth_source and created_at never change."""


class UserExists(ValueError):
    """Another account already has this username or email. `field` names which."""

    def __init__(self, field: Literal["username", "email"], value: str) -> None:
        super().__init__(f"a user with {field} {value!r} already exists")
        self.field = field


class LinkExists(ValueError):
    """This (provider, external_subject) is already linked to an account."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UserAccount:
    """One person's account, as stored.

    Fields:
        id: 32 hex characters — the service's key for this person, and the
            canonical Identity.subject.
        username: the login name, lowercased; unique.
        email: lowercased, or None; unique when set.
        email_verified: the address was confirmed by link, or vouched for by
            the IdP that supplied it.
        display_name: what the UI greets them with, or None.
        active: False refuses every sign-in and every request.
        password_hash: a bcrypt hash for local sign-in, or None (IdP-only
            accounts have none). Left out of repr.
        auth_source: the provider that created the account ("local",
            "authentik", ...). Informational; never changes.
        created_at, updated_at: UTC.
        last_login_at: the last sign-in (or, behind an IdP, the last request
            within the policy's touch interval), UTC, or None.
    """

    id: str
    username: str
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = None
    active: bool = True
    password_hash: str | None = field(default=None, repr=False)
    auth_source: str = LOCAL_PROVIDER
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    @property
    def name(self) -> str:
        """display_name, falling back to username — the label for a list or a timeline."""
        return self.display_name or self.username


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkedIdentity:
    """An external sign-in tied to an account.

    Fields:
        provider: Identity.provider of the source ("authentik", "oidc:<name>").
        external_subject: the source's own immutable id for the person.
        user_id: the UserAccount.id it signs in as.
        created_at: UTC.
        last_seen_at: the last time it resolved (within the touch interval), or None.
    """

    provider: str
    external_subject: str
    user_id: str
    created_at: datetime
    last_seen_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProvisioningPolicy:
    """How `resolve_account` treats an external sign-in it has no link for,
    and what it keeps in step on each one.

    Fields:
        auto_provision: create an account (and its link) on first sign-in.
            False makes an unlinked sign-in resolve to None, so accounts
            have to exist (and be linked) first — e.g. pushed by SCIM.
        link_by_verified_email: before provisioning, link to an existing
            account whose email matches the sign-in's *verified* email. Off
            by default: only turn it on when the IdP is the one place
            addresses are verified, since it hands that account over to
            whoever controls the address.
        idp_owned: the account fields the IdP is the source of truth for —
            copied from each sign-in when they differ. Any of "email",
            "display_name", "username".
        touch_interval: how stale last_seen_at/last_login_at may get before
            a sign-in writes them again; forward-auth resolves on every
            request, and this keeps that to one write per interval.
    """

    auto_provision: bool = True
    link_by_verified_email: bool = False
    idp_owned: frozenset[str] = frozenset({"email", "display_name"})
    touch_interval: timedelta = timedelta(hours=1)


ResolutionOutcome = Literal["existing", "synced", "linked", "provisioned"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Resolution:
    """What `resolve_account` found: the account, and how it got there —
    "existing" (nothing changed), "synced" (IdP-owned fields were copied in),
    "linked" (an existing account gained this link) or "provisioned" (a new
    account). An adapter can audit anything but "existing"."""

    account: UserAccount
    outcome: ResolutionOutcome


def normalize_username(username: str) -> str:
    """`username` stripped and lowercased. Raises ValueError when that leaves
    nothing, or when it's longer than MAX_USERNAME or contains whitespace."""
    value = username.strip().lower()
    if not value:
        raise ValueError("a username can't be empty")
    if len(value) > MAX_USERNAME or any(ch.isspace() for ch in value):
        raise ValueError("a username has no spaces and is at most 255 characters")
    return value


def normalize_email(email: str | None) -> str | None:
    """`email` stripped and lowercased, or None for None/blank. Raises
    ValueError for one without a single "@" between a local part and a
    domain, or longer than MAX_EMAIL."""
    if email is None or not email.strip():
        return None
    value = email.strip().lower()
    local, at, domain = value.rpartition("@")
    if not at or not local or not domain or len(value) > MAX_EMAIL or " " in value:
        raise ValueError(f"{email!r} isn't an email address")
    return value


def clean_display_name(value: str | None) -> str | None:
    """`value` stripped, or None for None/blank. Raises ValueError past MAX_DISPLAY_NAME."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > MAX_DISPLAY_NAME:
        raise ValueError("a display name is at most 255 characters")
    return value


def new_account(
    username: str,
    *,
    now: datetime,
    email: str | None = None,
    email_verified: bool = False,
    display_name: str | None = None,
    password_hash: str | None = None,
    auth_source: str = LOCAL_PROVIDER,
) -> UserAccount:
    """A new, checked UserAccount — what a store's `create` adds. Raises
    ValueError as normalize_username/normalize_email do. An account without
    an email is never verified."""
    now = aware(now)
    email = normalize_email(email)
    return UserAccount(
        id=uuid.uuid4().hex,
        username=normalize_username(username),
        email=email,
        email_verified=email_verified and email is not None,
        display_name=clean_display_name(display_name),
        password_hash=password_hash,
        auth_source=auth_source,
        created_at=now,
        updated_at=now,
    )


def apply_changes(
    account: UserAccount, changes: Mapping[str, Any], *, now: datetime
) -> UserAccount:
    """`account` with `changes` applied and checked — the rule every
    `UserStore.update` follows. Raises ValueError for a key outside UPDATABLE
    or a value normalize_* refuses.

    A changed email is unverified unless `changes` sets email_verified too
    (an IdP vouching for its new address); clearing it clears the flag.
    updated_at moves to `now` unless the only change is last_login_at, so
    "last changed" stays meaningful behind forward-auth.
    """
    unknown = set(changes) - UPDATABLE
    if unknown:
        raise ValueError(f"can't update {', '.join(sorted(unknown))}")
    values = dict(changes)
    if "username" in values:
        values["username"] = normalize_username(values["username"])
    if "display_name" in values:
        values["display_name"] = clean_display_name(values["display_name"])
    if "email" in values:
        values["email"] = normalize_email(values["email"])
        if values["email"] != account.email and "email_verified" not in values:
            values["email_verified"] = False
    if values.get("email", account.email) is None and (
        account.email_verified or "email_verified" in values
    ):
        values["email_verified"] = False
    if values.get("last_login_at") is not None:
        values["last_login_at"] = aware(values["last_login_at"])
    if set(values) - {"last_login_at"}:
        values["updated_at"] = aware(now)
    return replace(account, **values)


def account_identity(account: UserAccount, external: Identity | None = None) -> Identity:
    """The canonical Identity for `account`: subject is the account id and the
    profile fields come from the account. `external` (the sign-in it was
    resolved from) contributes its groups, claims and provider; without one
    (a local sign-in) they're empty and "local"."""
    return Identity(
        subject=account.id,
        username=account.username,
        email=account.email,
        groups=list(external.groups) if external else [],
        claims=dict(external.claims) if external else {},
        display_name=account.display_name,
        email_verified=account.email_verified,
        provider=external.provider if external else LOCAL_PROVIDER,
    )


def synced_changes(
    account: UserAccount, external: Identity, idp_owned: frozenset[str]
) -> dict[str, Any]:
    """The changes that bring `account`'s IdP-owned fields in line with
    `external` — empty when they already match. A field the sign-in left
    blank is never cleared: an IdP that stops sending a name hasn't
    necessarily removed it."""
    changes: dict[str, Any] = {}
    if "email" in idp_owned and external.email:
        email = normalize_email(external.email)
        if email != account.email or (external.email_verified and not account.email_verified):
            changes["email"] = email
            changes["email_verified"] = external.email_verified
    if "display_name" in idp_owned and external.display_name:
        name = clean_display_name(external.display_name)
        if name != account.display_name:
            changes["display_name"] = name
    if "username" in idp_owned and external.username:
        username = normalize_username(external.username)
        if username != account.username:
            changes["username"] = username
    return changes


def is_stale(seen: datetime | None, now: datetime, interval: timedelta) -> bool:
    """Whether a last_seen/last_login of `seen` is due a fresh write at `now`."""
    return seen is None or aware(now) - aware(seen) >= interval
