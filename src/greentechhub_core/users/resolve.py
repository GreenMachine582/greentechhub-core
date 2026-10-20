"""users.resolve — the two ways a caller becomes an account: `authenticate`
(a local username and password) and `resolve_account` (an Identity some
other source vouched for — forward-auth headers, an OIDC callback, a dev
token). Both are plain functions over any UserStore, so every store shares
one copy of the rules.

Each comes as an async function plus a `_sync` twin. The rules are written
once, as the async version; the twin drives that same coroutine over the
store's `_sync` methods (see _drive), which never suspend.
"""

import functools
from collections.abc import Callable, Coroutine, Mapping
from typing import Any

from greentechhub_core.identity.models import Identity
from greentechhub_core.security.passwords import hash_password, verify_password
from greentechhub_core.users.model import (
    LOCAL_PROVIDER,
    LinkExists,
    ProvisioningPolicy,
    Resolution,
    ResolutionOutcome,
    UserAccount,
    UserExists,
    clean_display_name,
    is_stale,
    normalize_email,
    normalize_username,
    synced_changes,
)
from greentechhub_core.users.store import UserStore

_DEFAULT_POLICY = ProvisioningPolicy()
_MAX_USERNAME_TRIES = 50


@functools.cache
def _dummy_hash() -> str:
    """A hash to check a password against when there's no account, so an
    unknown username takes as long as a wrong password."""
    return hash_password("not-a-real-password")


class _SyncAsAsync:
    """A store's `_sync` methods behind awaitable names, for _drive."""

    def __init__(self, store: UserStore) -> None:
        self._store = store

    def now(self):
        return self._store.now()

    def __getattr__(self, name: str):
        method = getattr(self._store, f"{name}_sync")

        async def call(*args: Any, **kwargs: Any) -> Any:
            return method(*args, **kwargs)

        return call


def _drive[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run `coro` to completion without an event loop. Only valid when
    nothing it awaits ever suspends — true over _SyncAsAsync."""
    try:
        coro.send(None)
    except StopIteration as done:
        return done.value
    coro.close()
    raise RuntimeError("a _sync users function awaited something that suspended")


async def authenticate(store: UserStore, username: str, password: str) -> UserAccount | None:
    """The active account `username` signs in as with `password`, with
    last_login_at set to now — or None for an unknown username, a wrong
    password, an inactive account or one without a password (IdP-only).
    Every refusal checks a password hash, so they all take as long."""
    try:
        account = await store.by_username(username)
    except ValueError:
        account = None
    hashed = account.password_hash if account is not None else None
    matches = verify_password(password, hashed or _dummy_hash())
    if account is None or not account.active or hashed is None or not matches:
        return None
    return await store.update(account.id, {"last_login_at": store.now()})


def authenticate_sync(store: UserStore, username: str, password: str) -> UserAccount | None:
    return _drive(authenticate(_SyncAsAsync(store), username, password))  # type: ignore[arg-type]


async def set_password(store: UserStore, user_id: str, password: str | None) -> UserAccount | None:
    """Hash and store `password` for `user_id` (None removes it, leaving IdP
    sign-in only). Returns the updated account, or None for an unknown id."""
    hashed = hash_password(password) if password is not None else None
    return await store.update(user_id, {"password_hash": hashed})


def set_password_sync(store: UserStore, user_id: str, password: str | None) -> UserAccount | None:
    return _drive(set_password(_SyncAsAsync(store), user_id, password))  # type: ignore[arg-type]


async def resolve_account(
    store: UserStore, external: Identity, policy: ProvisioningPolicy = _DEFAULT_POLICY
) -> Resolution | None:
    """The account `external` signs in as, or None when it's inactive, or
    unlinked and `policy` won't provision it.

    A "local" Identity's subject already is an account id (the service's own
    sign-in issued it), so it's only looked up. Any other provider is looked
    up by its link, (external.provider, external.subject):
      - linked: the policy's idp_owned fields are synced from `external`
        ("synced"), else nothing changes ("existing").
      - unlinked, with link_by_verified_email and a verified email that an
        account has: that account gains the link ("linked"), then syncs.
      - unlinked, with auto_provision: a new account and its link are
        created together ("provisioned"). Its username is external.username,
        suffixed "-2", "-3", ... when taken; an email another account holds
        is left off rather than refusing the sign-in.
    The link's last_seen_at and the account's last_login_at are written at
    most once per policy.touch_interval.
    """
    if external.provider == LOCAL_PROVIDER:
        account = await store.get(external.subject)
        if account is None or not account.active:
            return None
        return Resolution(account=account, outcome="existing")

    outcome: ResolutionOutcome = "existing"
    link = await store.find_link(external.provider, external.subject)
    if link is not None:
        account = await store.get(link.user_id)
    else:
        account = None
        if policy.link_by_verified_email and external.email_verified and external.email:
            account = await store.by_email(external.email)
        if account is not None:
            try:
                link = await store.link(account.id, external.provider, external.subject)
                outcome = "linked"
            except LinkExists:
                return await resolve_account(store, external, policy)
        elif policy.auto_provision:
            created = await _provision(store, external)
            if created is None:
                return await resolve_account(store, external, policy)
            await store.touch_link(external.provider, external.subject)
            created = await store.update(created.id, {"last_login_at": store.now()}) or created
            return Resolution(account=created, outcome="provisioned")
    if account is None or not account.active:
        return None

    changes = _safe_sync_changes(account, external, policy)
    synced = bool(changes)
    now = store.now()
    if link is not None and is_stale(link.last_seen_at, now, policy.touch_interval):
        await store.touch_link(external.provider, external.subject)
        changes["last_login_at"] = now
    if changes:
        account = await _update_dropping_taken(store, account, changes)
    if synced and outcome == "existing":
        outcome = "synced"
    return Resolution(account=account, outcome=outcome)


def resolve_account_sync(
    store: UserStore, external: Identity, policy: ProvisioningPolicy = _DEFAULT_POLICY
) -> Resolution | None:
    return _drive(resolve_account(_SyncAsAsync(store), external, policy))  # type: ignore[arg-type]


def _safe_sync_changes(
    account: UserAccount, external: Identity, policy: ProvisioningPolicy
) -> dict[str, Any]:
    """synced_changes, field by field, skipping any value the IdP sent that
    an account can't hold (a malformed address, an over-long name)."""
    changes: dict[str, Any] = {}
    for field in policy.idp_owned:
        try:
            changes.update(synced_changes(account, external, frozenset({field})))
        except ValueError:
            continue
    return changes


async def _update_dropping_taken(
    store: UserStore, account: UserAccount, changes: Mapping[str, Any]
) -> UserAccount:
    """Apply `changes`, leaving out a username or email another account
    already holds, so a clash never refuses the sign-in."""
    pending = dict(changes)
    while True:
        try:
            updated = await store.update(account.id, pending)
            return updated if updated is not None else account
        except UserExists as clash:
            pending.pop(clash.field, None)
            if clash.field == "email":
                pending.pop("email_verified", None)
            if not pending:
                return account


async def _provision(store: UserStore, external: Identity) -> UserAccount | None:
    """Create the account and link for `external` together, or None when a
    concurrent sign-in linked it first (the caller looks it up again)."""
    base = _valid(normalize_username, external.username) or "user"
    email = _valid(normalize_email, external.email)
    fields: dict[str, Any] = {
        "email": email,
        "email_verified": external.email_verified and email is not None,
        "display_name": _valid(clean_display_name, external.display_name),
        "auth_source": external.provider,
    }
    attempt = 1
    while attempt <= _MAX_USERNAME_TRIES:
        candidate = base if attempt == 1 else f"{base[:240]}-{attempt}"
        try:
            return await store.create(
                candidate, link=(external.provider, external.subject), **fields
            )
        except LinkExists:
            return None
        except UserExists as clash:
            if clash.field == "email" and fields["email"] is not None:
                fields["email"], fields["email_verified"] = None, False
            else:
                attempt += 1
    raise RuntimeError(f"no free username for {external.username!r}")


def _valid[T](normalize: Callable[[Any], T], value: Any) -> T | None:
    """normalize(value), or None when it refuses it."""
    try:
        return normalize(value)
    except ValueError:
        return None
