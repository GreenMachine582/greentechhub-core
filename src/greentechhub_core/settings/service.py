"""settings.service — Settings: the facade a service (or its adapter) talks
to, joining a SettingsRegistry, a SettingsStore and the env overrides —
see docs/settings.md.

Reads resolve user → app → env → default (resolution.py). Writes validate
against the registry before anything reaches the store, so a store only
ever holds values that were valid when written.

This module doesn't import permissions/ or identity/: `identity` is anything
with a `subject`, and `granted` is any collection of permission strings,
e.g. the frozenset RoleResolver.granted returns.
"""

from collections.abc import Collection, Mapping
from typing import Protocol

from greentechhub_core.settings.definitions import Setting, SettingScope, SettingValue
from greentechhub_core.settings.registry import SettingsRegistry
from greentechhub_core.settings.resolution import DEFAULT_ENV_PREFIX
from greentechhub_core.settings.store import SettingsStore


class SubjectLike(Protocol):
    """The one identity field Settings reads. core's Identity fits as-is."""

    @property
    def subject(self) -> str: ...


class SettingPermissionError(PermissionError):
    """A write the caller isn't allowed to make: an app value without the
    setting's `edit_permission`, or a user value with no signed-in user.
    `permission` is the missing permission, or None for the anonymous case.
    An adapter maps this to 403 (or 401 when `permission` is None).
    """

    def __init__(self, key: str, permission: str | None) -> None:
        self.key = key
        self.permission = permission
        if permission is None:
            message = f"setting {key!r}: an anonymous user has no preferences to change"
        else:
            message = f"setting {key!r}: changing the app value needs {permission!r}"
        super().__init__(message)


class Settings:
    """Read and write setting values for a service.

    Args:
        registry: the service's SettingsRegistry.
        store: where values live.
        env: env overrides, keyed by setting key. Defaults to
            `registry.env_overrides(prefix=env_prefix)`, read once here, so
            a malformed env value fails at startup.
        env_prefix: the env var prefix when `env` isn't given.

    Every method comes as an async one plus a `_sync` twin, calling the
    store's matching pair.

    Reads: `effective(identity)` gives every registered setting's value for
    that person; `get(key, identity)` gives one. `identity=None`
    (anonymous) skips the user layer.

    Writes: `set_user`/`reset_user` change the caller's own value for a
    USER setting. `set_app`/`reset_app` change the service-wide value of
    any setting (for a USER setting, the default everyone without their own
    value sees) and need `granted` to contain the setting's
    `edit_permission` when it has one. A setting with no `edit_permission`
    is left to the caller to guard, e.g. by only exposing the admin form to
    admins. `granted` is required either way so every app write says what
    the caller holds.

    Errors: an unknown key raises KeyError, an invalid value ValueError
    (from Setting.validate; use `registry.coerce` first for form strings),
    set_user on an APP setting ValueError, and a denied write
    SettingPermissionError.
    """

    def __init__(
        self,
        registry: SettingsRegistry,
        store: SettingsStore,
        *,
        env: Mapping[str, SettingValue] | None = None,
        env_prefix: str = DEFAULT_ENV_PREFIX,
    ) -> None:
        self.registry = registry
        self.store = store
        self._env = dict(env) if env is not None else registry.env_overrides(prefix=env_prefix)

    # reads

    def effective_sync(self, identity: SubjectLike | None = None) -> dict[str, SettingValue]:
        app = self.store.get_many_sync(SettingScope.APP, None)
        user = self._user_values_sync(identity)
        return self.registry.resolve_all(user=user, app=app, env=self._env)

    async def effective(self, identity: SubjectLike | None = None) -> dict[str, SettingValue]:
        app = await self.store.get_many(SettingScope.APP, None)
        user = await self._user_values(identity)
        return self.registry.resolve_all(user=user, app=app, env=self._env)

    def get_sync(self, key: str, identity: SubjectLike | None = None) -> SettingValue:
        setting = self.registry.get(key)
        app = self.store.get_many_sync(SettingScope.APP, None)
        user = self._user_values_sync(identity) if setting.scope is SettingScope.USER else None
        return self.registry.resolve(key, user=user, app=app, env=self._env)

    async def get(self, key: str, identity: SubjectLike | None = None) -> SettingValue:
        setting = self.registry.get(key)
        app = await self.store.get_many(SettingScope.APP, None)
        user = await self._user_values(identity) if setting.scope is SettingScope.USER else None
        return self.registry.resolve(key, user=user, app=app, env=self._env)

    def _user_values_sync(self, identity: SubjectLike | None) -> dict[str, SettingValue] | None:
        if identity is None:
            return None
        return self.store.get_many_sync(SettingScope.USER, identity.subject)

    async def _user_values(self, identity: SubjectLike | None) -> dict[str, SettingValue] | None:
        if identity is None:
            return None
        return await self.store.get_many(SettingScope.USER, identity.subject)

    # user writes

    def _user_setting(self, identity: SubjectLike | None, key: str) -> Setting:
        setting = self.registry.get(key)
        if setting.scope is not SettingScope.USER:
            raise ValueError(f"setting {key!r} is app-scoped; use set_app")
        if identity is None:
            raise SettingPermissionError(key, None)
        return setting

    def set_user_sync(self, identity: SubjectLike | None, key: str, value: object) -> None:
        value = self._user_setting(identity, key).validate(value)
        self.store.set_sync(SettingScope.USER, identity.subject, key, value)

    async def set_user(self, identity: SubjectLike | None, key: str, value: object) -> None:
        value = self._user_setting(identity, key).validate(value)
        await self.store.set(SettingScope.USER, identity.subject, key, value)

    def reset_user_sync(self, identity: SubjectLike | None, key: str) -> None:
        """Drop the user's own value, so they see the app value again."""
        self._user_setting(identity, key)
        self.store.delete_sync(SettingScope.USER, identity.subject, key)

    async def reset_user(self, identity: SubjectLike | None, key: str) -> None:
        self._user_setting(identity, key)
        await self.store.delete(SettingScope.USER, identity.subject, key)

    # app writes

    def _app_setting(self, key: str, granted: Collection[str]) -> Setting:
        setting = self.registry.get(key)
        if setting.edit_permission is not None and setting.edit_permission not in granted:
            raise SettingPermissionError(key, setting.edit_permission)
        return setting

    def set_app_sync(self, key: str, value: object, *, granted: Collection[str]) -> None:
        value = self._app_setting(key, granted).validate(value)
        self.store.set_sync(SettingScope.APP, None, key, value)

    async def set_app(self, key: str, value: object, *, granted: Collection[str]) -> None:
        value = self._app_setting(key, granted).validate(value)
        await self.store.set(SettingScope.APP, None, key, value)

    def reset_app_sync(self, key: str, *, granted: Collection[str]) -> None:
        """Drop the app value, so the env override or default applies."""
        self._app_setting(key, granted)
        self.store.delete_sync(SettingScope.APP, None, key)

    async def reset_app(self, key: str, *, granted: Collection[str]) -> None:
        self._app_setting(key, granted)
        await self.store.delete(SettingScope.APP, None, key)
