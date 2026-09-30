"""settings.store — SettingsStore (stored setting values) with
InMemorySettingsStore and JsonFileSettingsStore, its reference
implementations — see docs/settings.md.

A stored value belongs to an owner: `(SettingScope.APP, None)` for the
service-wide value, or `(SettingScope.USER, subject)` for one person's,
keyed on `Identity.subject` like GrantStore. Within an owner, values are
keyed by setting key.

A store doesn't know the registry. It keeps whatever JSON-compatible value
(bool, int or str) it's given and hands it back as-is; the Settings facade
(service.py) validates before writing, and resolution skips anything that
no longer validates on the way out. A service that wants its rows in its own
database implements this protocol over its own tables.
"""

import json
import os
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from greentechhub_core.settings.definitions import SettingScope, SettingValue


def check_owner(scope: SettingScope, subject: str | None) -> SettingScope:
    """Normalise `scope` and raise ValueError unless the owner is well
    formed: APP values have no subject, USER values need a non-empty one.
    Every store calls this, so a mixed-up owner fails loudly rather than
    writing a row nobody reads back.
    """
    scope = SettingScope(scope)
    if scope is SettingScope.APP and subject is not None:
        raise ValueError("an app-scoped value has no subject")
    if scope is SettingScope.USER and not subject:
        raise ValueError("a user-scoped value needs a subject")
    return scope


class SettingsStore(Protocol):
    """Structural contract for a setting-value store, with async methods and
    `_sync` twins like GrantStore.

    Semantics every implementation keeps (SettingsStoreContract asserts
    them):
      - `get_many` returns every value stored for the owner, as a new dict;
        an owner with nothing stored gets `{}`.
      - `set` inserts or overwrites one value.
      - `delete` of a key that isn't stored is a no-op.
      - owners are isolated: app values, and each subject's user values,
        never show up under another owner.
      - an APP owner with a subject, or a USER owner without one, raises
        ValueError (see check_owner).
    """

    async def get_many(
        self, scope: SettingScope, subject: str | None
    ) -> dict[str, SettingValue]: ...

    def get_many_sync(
        self, scope: SettingScope, subject: str | None
    ) -> dict[str, SettingValue]: ...

    async def set(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None: ...

    def set_sync(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None: ...

    async def delete(self, scope: SettingScope, subject: str | None, key: str) -> None: ...

    def delete_sync(self, scope: SettingScope, subject: str | None, key: str) -> None: ...


class _SyncBackedStore:
    """The async methods for a store with no I/O worth awaiting: each one
    delegates to its `_sync` twin, as InMemoryGrantStore does."""

    async def get_many(self, scope: SettingScope, subject: str | None) -> dict[str, SettingValue]:
        return self.get_many_sync(scope, subject)

    async def set(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None:
        self.set_sync(scope, subject, key, value)

    async def delete(self, scope: SettingScope, subject: str | None, key: str) -> None:
        self.delete_sync(scope, subject, key)


class InMemorySettingsStore(_SyncBackedStore):
    """A process-local SettingsStore: a dict per owner behind a lock. For
    tests, single-process tools, and as the executable reference the
    contract is checked against. Nothing persists across restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[tuple[SettingScope, str | None], dict[str, SettingValue]] = {}

    def get_many_sync(self, scope: SettingScope, subject: str | None) -> dict[str, SettingValue]:
        owner = (check_owner(scope, subject), subject)
        with self._lock:
            return dict(self._values.get(owner, {}))

    def set_sync(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None:
        owner = (check_owner(scope, subject), subject)
        with self._lock:
            self._values.setdefault(owner, {})[key] = value

    def delete_sync(self, scope: SettingScope, subject: str | None, key: str) -> None:
        owner = (check_owner(scope, subject), subject)
        with self._lock:
            values = self._values.get(owner)
            if values is None:
                return
            values.pop(key, None)
            if not values:
                del self._values[owner]


class JsonFileSettingsStore(_SyncBackedStore):
    """A SettingsStore kept in one JSON file, for small services and tools
    that have no database:

        {"app": {"site.banner": "..."}, "user": {"<subject>": {"ui.theme": "dark"}}}

    Every call reads the file, so edits made by hand or by another process
    show up without a restart. Writes replace the file atomically (a temp
    file in the same directory, then os.replace), so a reader never sees a
    half-written file. A lock serialises this process's own
    read-modify-write cycles; there's no cross-process lock, so run one
    writer per file.

    A missing file reads as empty and is created on the first write, along
    with its parent directory. A file that isn't valid JSON of the shape
    above raises ValueError rather than being overwritten.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"app": {}, "user": {}}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self._path}: not valid JSON: {exc}") from None
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("app", {}), dict)
            or not isinstance(data.get("user", {}), dict)
            or not all(isinstance(v, dict) for v in data.get("user", {}).values())
        ):
            raise ValueError(f"{self._path}: expected {{'app': {{...}}, 'user': {{...}}}}")
        data.setdefault("app", {})
        data.setdefault("user", {})
        return data

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=f".{self._path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    @staticmethod
    def _owner_values(data: dict, scope: SettingScope, subject: str | None) -> Mapping:
        if scope is SettingScope.APP:
            return data["app"]
        return data["user"].get(subject, {})

    def get_many_sync(self, scope: SettingScope, subject: str | None) -> dict[str, SettingValue]:
        scope = check_owner(scope, subject)
        with self._lock:
            return dict(self._owner_values(self._read(), scope, subject))

    def set_sync(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None:
        scope = check_owner(scope, subject)
        with self._lock:
            data = self._read()
            if scope is SettingScope.APP:
                data["app"][key] = value
            else:
                data["user"].setdefault(subject, {})[key] = value
            self._write(data)

    def delete_sync(self, scope: SettingScope, subject: str | None, key: str) -> None:
        scope = check_owner(scope, subject)
        with self._lock:
            data = self._read()
            values = data["app"] if scope is SettingScope.APP else data["user"].get(subject)
            if values is None or key not in values:
                return
            del values[key]
            if scope is SettingScope.USER and not values:
                del data["user"][subject]
            self._write(data)
