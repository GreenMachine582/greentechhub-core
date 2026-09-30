"""settings.resolution — picking a setting's effective value from the
layers that can set it — see docs/settings.md.

Order, first valid value wins:
  1. user value (USER settings only; ignored for APP settings)
  2. app value — for a USER setting, the admin-set default for everyone
  3. env override — an env var, read once through read_env_overrides
  4. the definition's default

Each layer is a plain key → value mapping, so this module does no I/O and
doesn't care where the values came from. A stored value that no longer
validates (say, a choice removed from code while its rows remain) is skipped
and resolution falls through to the next layer, the same way RoleResolver
ignores stale grant rows. Env values are the exception to "skip quietly":
read_env_overrides raises on a malformed one, since env is config and a typo
should surface at startup.
"""

import os
from collections.abc import Iterable, Mapping

from greentechhub_core.settings.definitions import Setting, SettingScope, SettingValue

DEFAULT_ENV_PREFIX = "SETTING_"
"""The default env var prefix for overrides: "ui.page_size" is read from
SETTING_UI__PAGE_SIZE. Overridable per call, like feature_flags'
DEFAULT_ENV_PREFIX."""


def env_var_name(key: str, prefix: str = DEFAULT_ENV_PREFIX) -> str:
    """The env var that overrides `key`: prefix + key uppercased, with each
    "." turned into "__" (pydantic-settings' nested delimiter). Setting keys
    never contain "__", so the mapping can't collide.
    """
    return prefix + key.upper().replace(".", "__")


def read_env_overrides(
    settings: Iterable[Setting],
    environ: Mapping[str, str] | None = None,
    *,
    prefix: str = DEFAULT_ENV_PREFIX,
) -> dict[str, SettingValue]:
    """Coerce every env override present for `settings`, keyed by setting
    key. `environ` defaults to os.environ. Raises ValueError naming the env
    var when a value doesn't coerce.
    """
    environ = os.environ if environ is None else environ
    overrides: dict[str, SettingValue] = {}
    for setting in settings:
        name = env_var_name(setting.key, prefix)
        if name not in environ:
            continue
        try:
            overrides[setting.key] = setting.coerce(environ[name])
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    return overrides


def _valid(setting: Setting, layer: Mapping[str, object] | None) -> tuple[bool, SettingValue]:
    if layer is None or setting.key not in layer:
        return False, setting.default
    try:
        return True, setting.validate(layer[setting.key])
    except ValueError:
        return False, setting.default


def resolve(
    setting: Setting,
    *,
    user: Mapping[str, object] | None = None,
    app: Mapping[str, object] | None = None,
    env: Mapping[str, object] | None = None,
) -> SettingValue:
    """`setting`'s effective value from the user, app and env layers, else
    its default. Each layer maps setting keys to typed values.
    """
    layers = (app, env) if setting.scope is SettingScope.APP else (user, app, env)
    for layer in layers:
        found, value = _valid(setting, layer)
        if found:
            return value
    return setting.default
