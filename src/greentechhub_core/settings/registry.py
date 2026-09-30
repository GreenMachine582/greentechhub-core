"""settings.registry — SettingsRegistry: the service's catalogue of Setting
definitions, with lookup, validate/coerce by key, and resolution across
every registered setting — see docs/settings.md.

Opt-in: a registry starts empty. Nothing registers itself, built-ins
included — a service passes builtins.USER_PREFERENCES in if it wants them.
"""

from collections.abc import Iterable, Iterator, Mapping

from greentechhub_core.settings.definitions import Setting, SettingScope, SettingValue
from greentechhub_core.settings.resolution import (
    DEFAULT_ENV_PREFIX,
    read_env_overrides,
    resolve,
)


class SettingsRegistry:
    """A keyed collection of Setting definitions.

    Registration fails fast with ValueError on a duplicate key. Lookups by
    an unknown key raise KeyError. Iteration yields settings in
    registration order, which is the order a settings form lists them in.
    """

    def __init__(self, settings: Iterable[Setting] = ()) -> None:
        self._settings: dict[str, Setting] = {}
        self.register(*settings)

    def register(self, *settings: Setting) -> None:
        for setting in settings:
            if setting.key in self._settings:
                raise ValueError(f"duplicate setting key {setting.key!r}")
            self._settings[setting.key] = setting

    def get(self, key: str) -> Setting:
        try:
            return self._settings[key]
        except KeyError:
            raise KeyError(f"unknown setting {key!r}") from None

    def __contains__(self, key: object) -> bool:
        return key in self._settings

    def __iter__(self) -> Iterator[Setting]:
        return iter(self._settings.values())

    def __len__(self) -> int:
        return len(self._settings)

    def for_scope(self, scope: SettingScope) -> tuple[Setting, ...]:
        return tuple(s for s in self._settings.values() if s.scope is SettingScope(scope))

    def validate(self, key: str, value: object) -> SettingValue:
        """Setting.validate for the setting registered under `key`."""
        return self.get(key).validate(value)

    def coerce(self, key: str, raw: str) -> SettingValue:
        """Setting.coerce for the setting registered under `key`."""
        return self.get(key).coerce(raw)

    def env_overrides(
        self, environ: Mapping[str, str] | None = None, *, prefix: str = DEFAULT_ENV_PREFIX
    ) -> dict[str, SettingValue]:
        """resolution.read_env_overrides over every registered setting. Call
        it once at startup and pass the result as `env`: a malformed value
        raises there instead of on some later request.
        """
        return read_env_overrides(self, environ, prefix=prefix)

    def resolve(
        self,
        key: str,
        *,
        user: Mapping[str, object] | None = None,
        app: Mapping[str, object] | None = None,
        env: Mapping[str, object] | None = None,
    ) -> SettingValue:
        """The effective value of one setting — see resolution.resolve."""
        return resolve(self.get(key), user=user, app=app, env=env)

    def resolve_all(
        self,
        *,
        user: Mapping[str, object] | None = None,
        app: Mapping[str, object] | None = None,
        env: Mapping[str, object] | None = None,
        scope: SettingScope | None = None,
    ) -> dict[str, SettingValue]:
        """Effective values for every registered setting (or only `scope`'s),
        keyed by setting key. Keys in the layers that aren't registered are
        ignored.
        """
        settings = self if scope is None else self.for_scope(scope)
        return {s.key: resolve(s, user=user, app=app, env=env) for s in settings}
