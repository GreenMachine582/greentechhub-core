"""feature_flags.provider — FeatureFlagProvider protocol and
EnvFileFeatureFlagProvider, the first of (at least) two implementations
docs/modules.md calls for: "Same evolve-the-adapter shape as identity —
starts as env/static-file-backed (FeatureFlagProvider protocol), room for a
real flag service later without call-site changes."

One deliberate departure from that "same shape as identity" lineage:
FeatureFlagProvider has no is_enabled/is_enabled_sync split the way
identity.IdentityProvider has resolve/resolve_sync. A flag check is a
hot-path call (routinely made many times per request), unlike identity
resolution (once per request); every mainstream flag SDK (LaunchDarkly,
Unleash, Flagsmith, ConfigCat) answers a flag check synchronously from a
locally-cached, background-refreshed store rather than blocking each check
on network I/O — a future real-flag-service implementation of this Protocol
is expected to do the same, so there's no future need for an async method
here, unlike identity's plausible per-call OIDC round trip.
"""

import json
import os
from pathlib import Path
from typing import Protocol

DEFAULT_ENV_PREFIX = "FEATURE_"
"""The default env var prefix EnvFileFeatureFlagProvider looks flags up
under (e.g. flag "new-ui" -> env var "FEATURE_NEW_UI"). Exported as a public
constant, and overridable per-instance via `env_prefix`, matching
security.redact.DEFAULT_SECRET_KEYS' own caller-overridable-default pattern.
"""

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


class FeatureFlagProvider(Protocol):
    """Structural contract every feature-flag source implements — see
    docs/modules.md. A typing.Protocol, not an ABC: identical reasoning to
    identity.provider.IdentityProvider's own docstring — nothing in this
    ecosystem needs isinstance(x, FeatureFlagProvider) (Result remains the
    one ABC exception here, for Ok/Err isinstance checks), so a plain class
    matching this shape by structure satisfies it without declared
    inheritance.
    """

    def is_enabled(self, name: str, *, default: bool = False) -> bool:
        """Return whether the flag `name` is enabled.

        `default` is keyword-only specifically so a future signature
        addition (e.g. an optional keyword-only `identity`/`context`
        parameter for per-user targeting — out of scope for v1, the same
        "nothing else is confirmed-needed, speculative fields risk guessing
        wrong" reasoning identity.models.RawAuthContext's docstring applies)
        can be added without breaking any existing call site — the concrete
        "evolve... without call-site changes" property docs/modules.md
        promises.
        """
        ...


class EnvFileFeatureFlagProvider:
    """Reads flags from real environment variables and, optionally, a flat
    JSON file — the "env/static-file-backed" implementation docs/modules.md
    calls for. One implementation covering both sources, not two separate
    provider classes: docs/modules.md's own wording ("env/static-file-
    backed") describes a single adapter checking both, not two.

    Precedence: a real environment variable always wins over the file,
    which wins over `default` — reusing, not reinventing,
    config.base_settings.GTHBaseSettings' own documented rule verbatim
    ("real env vars always win").

    Does not build on GTHBaseSettings/pydantic-settings: a Settings
    subclass declares a fixed, known-ahead-of-time set of fields, while flag
    names are an open-ended set only known at each is_enabled() call site —
    the same "unbounded set of valid values" situation
    permissions.catalogue.Permission is in for permission strings, and
    pydantic-settings has no way to model "any key the file happens to
    contain." Reads `os.environ` and the JSON file directly via stdlib
    os/json/pathlib instead, which also means this module doesn't import
    greentechhub_core.config — matching identity.provider.
    DevelopmentIdentityProvider's own choice not to import `config` for its
    `secret_key`.

    File flags are loaded eagerly, once, at construction — not lazily on
    every is_enabled() call: the file's flag set is finite and fully
    enumerable up front (the JSON object's own keys), so it's loaded and
    validated fail-fast at construction. There is no live reload; a service
    needing changed file flags reconstructs the provider. Env flags, by
    contrast, are looked up fresh on every is_enabled() call: the env
    namespace is open-ended (there's no way to "preload every possible env
    var" the way the file's keys can be preloaded), so a per-call
    os.environ.get(...) lookup is a structural necessity, not merely a
    testing convenience.

    Malformed configuration fails fast and loudly, not silently: a missing
    explicitly-given file, invalid JSON, a non-object top-level value, a
    non-bool value under some key, or an unrecognized env var string all
    raise, at the point of failure. This is deliberately not the
    "malformed input degrades to a safe sentinel" treatment
    DevelopmentIdentityProvider/security.passwords.verify_password give
    genuinely untrusted *external* input — a feature-flags file or env var
    is caller-authored local configuration (the same category
    security.passwords.hash_password's `rounds` argument is in), and a flag
    silently resolving to a wrong default because of an unnoticed typo
    (`FEATURE_X=enbaled`) is a worse, harder-to-debug outcome than a loud
    startup/call-site crash.
    """

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        env_prefix: str = DEFAULT_ENV_PREFIX,
    ) -> None:
        self._env_prefix = env_prefix
        self._file_flags: dict[str, bool] = (
            _load_file_flags(Path(path)) if path is not None else {}
        )

    def is_enabled(self, name: str, *, default: bool = False) -> bool:
        """See FeatureFlagProvider.is_enabled. Checks the environment
        first, then the loaded file, then falls back to `default`.
        """
        raw_env_value = os.environ.get(self._env_var_name(name))
        if raw_env_value is not None:
            return _parse_bool(raw_env_value, name=name)

        if name in self._file_flags:
            return self._file_flags[name]

        return default

    def _env_var_name(self, name: str) -> str:
        """The env var `name` resolves under: this provider's `env_prefix`
        plus `name` uppercased with hyphens replaced by underscores (POSIX
        env var names can't contain hyphens; case is normalized to upper
        since every existing env var in this ecosystem, e.g. SECRET_KEY, is
        SCREAMING_CASE, per GTHBaseSettings' own convention).
        """
        return f"{self._env_prefix}{name.upper().replace('-', '_')}"


def _load_file_flags(path: Path) -> dict[str, bool]:
    """Read and validate `path` as a flat JSON object of flag-name -> bool.

    Raises FileNotFoundError (via Path.read_text, uncaught — already a
    clear, standard error) if `path` doesn't exist. Raises ValueError,
    naming `path`, for invalid JSON, a non-object top-level value, or a
    non-bool value under some key (naming the offending key too) — see
    EnvFileFeatureFlagProvider's own docstring for why these fail loudly
    rather than degrading.
    """
    text = path.read_text(encoding="utf-8")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"feature flags file {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"feature flags file {path} must contain a JSON object, got {type(data).__name__}"
        )

    for key, value in data.items():
        if not isinstance(value, bool):
            raise ValueError(
                f"feature flags file {path}: flag {key!r} must be a JSON bool, "
                f"got {type(value).__name__}"
            )

    return data


def _parse_bool(raw: str, *, name: str) -> bool:
    """Parse an env var string as a bool, case-insensitively matching common
    truthy (true/1/yes/on) and falsy (false/0/no/off) spellings.

    Raises ValueError, naming `name` and the offending raw value, for
    anything else — see EnvFileFeatureFlagProvider's own docstring for why
    an unrecognized value fails loudly instead of silently falling back to
    `default`.
    """
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(
        f"feature flag {name!r}: unrecognized value {raw!r}; expected one of "
        f"{sorted(_TRUE_VALUES | _FALSE_VALUES)}"
    )
