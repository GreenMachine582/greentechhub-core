"""permissions.grants — GrantStore (per-subject role assignments) and
InMemoryGrantStore, its reference implementation — see docs/permissions.md.

A grant is a (subject, role name) pair: "this person holds this role in this
service", assigned in-app rather than derived from a directory group. Keyed
on `Identity.subject`, never on groups, so grants work with local auth alone
— no Authentik required.

This module defines the store's shape, not where the rows live. A service
that wants persistent grants keeps them in its own database (a store
implementing this protocol over its own tables); InMemoryGrantStore is for
tests, single-process tools, and as the executable reference the
GrantStoreContract (contracts/permissions.py) is checked against. Role names
are plain strings here — the store doesn't know the service's Role catalogue;
RoleResolver (resolver.py) maps names to Roles and ignores any it doesn't
know.
"""

import threading
from collections.abc import Mapping
from typing import Protocol


class GrantStore(Protocol):
    """Structural contract for a per-subject role-assignment store. A
    `typing.Protocol` for the same reason IdentityProvider is one: nothing
    needs `isinstance`, so any class of this shape satisfies it.

    Each operation comes as an async method plus a `_sync` twin, mirroring
    IdentityProvider's `resolve`/`resolve_sync` pair, so web services and
    sync tools (bots, CLIs) share one store.

    Semantics every implementation keeps (GrantStoreContract asserts them):
      - `roles_for` of an unknown subject is an empty frozenset, not an error.
      - `assign` is idempotent — assigning a held role again is a no-op.
      - `revoke` of a role the subject doesn't hold is a no-op.
      - `list_assignments` maps each subject holding at least one role to
        its roles; subjects with none are absent.
    """

    async def roles_for(self, subject: str) -> frozenset[str]: ...

    def roles_for_sync(self, subject: str) -> frozenset[str]: ...

    async def assign(self, subject: str, role: str) -> None: ...

    def assign_sync(self, subject: str, role: str) -> None: ...

    async def revoke(self, subject: str, role: str) -> None: ...

    def revoke_sync(self, subject: str, role: str) -> None: ...

    async def list_assignments(self) -> Mapping[str, frozenset[str]]: ...

    def list_assignments_sync(self) -> Mapping[str, frozenset[str]]: ...


class InMemoryGrantStore:
    """A process-local GrantStore — a dict of subject → role names behind a
    lock, so threaded servers and sync tools can share one instance safely.
    Nothing persists across restarts; a service wanting durable grants uses
    a database-backed store instead.

    Reads return frozen copies, never the live internal sets, so a caller
    can't mutate the store's state by accident. The async methods delegate
    to the sync ones: there's no I/O to await.
    """

    def __init__(self, assignments: Mapping[str, frozenset[str] | set[str]] | None = None) -> None:
        self._lock = threading.Lock()
        self._assignments: dict[str, set[str]] = {
            subject: set(roles) for subject, roles in (assignments or {}).items() if roles
        }

    def roles_for_sync(self, subject: str) -> frozenset[str]:
        with self._lock:
            return frozenset(self._assignments.get(subject, ()))

    def assign_sync(self, subject: str, role: str) -> None:
        with self._lock:
            self._assignments.setdefault(subject, set()).add(role)

    def revoke_sync(self, subject: str, role: str) -> None:
        with self._lock:
            roles = self._assignments.get(subject)
            if roles is None:
                return
            roles.discard(role)
            if not roles:
                del self._assignments[subject]

    def list_assignments_sync(self) -> Mapping[str, frozenset[str]]:
        with self._lock:
            return {subject: frozenset(roles) for subject, roles in self._assignments.items()}

    async def roles_for(self, subject: str) -> frozenset[str]:
        return self.roles_for_sync(subject)

    async def assign(self, subject: str, role: str) -> None:
        self.assign_sync(subject, role)

    async def revoke(self, subject: str, role: str) -> None:
        self.revoke_sync(subject, role)

    async def list_assignments(self) -> Mapping[str, frozenset[str]]:
        return self.list_assignments_sync()
