"""GTHBaseSettings — the pydantic-settings base class every GreenTechHub-ecosystem
service's own Settings extends.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GTHBaseSettings(BaseSettings):
    """Base settings shared by every GreenTechHub-ecosystem service.

    Values are read from real environment variables first, falling back to a
    ``.env`` file in the current working directory if present (real env vars
    always win, matching the ecosystem's existing python-dotenv convention).
    Field name matching against env vars is case-insensitive, so lowercase
    field names here (``secret_key``) resolve from SCREAMING_CASE env vars
    (``SECRET_KEY``) — and subclasses remain free to declare their own
    SCREAMING_CASE fields (e.g. ``ASYNC_DATABASE_URL``) without losing that
    matching.

    ``settings_cipher_key`` (``SETTINGS_CIPHER_KEY``) is the Fernet key that
    encrypts secret settings at rest. It's optional: left empty,
    settings.crypto.settings_cipher derives one from ``secret_key`` (with a
    warning), so a development setup needs only one secret.

    The adapter settings below are read by greentechhub-fastapi's
    ``register_*`` functions. They live here so a service gets them by
    extending this class: one it forgot to declare would otherwise be
    dropped without a word (a Settings with ``extra="ignore"``). Every default
    is the safe one, and the list-like ones are comma-separated strings:

    - ``auth_adapter`` (``AUTH_ADAPTER``): "local" (the default; the service
      signs its own session cookie) or "forward_auth" (a reverse proxy such
      as Authentik's outpost signs people in). ``register_auth``.
    - ``cors_allowed_origins`` (``CORS_ALLOWED_ORIGINS``): origins allowed
      cross-origin requests; empty allows none. ``register_core``.
    - ``trusted_proxies`` (``TRUSTED_PROXIES``): addresses of the reverse
      proxies in front of the service, whose ``X-Forwarded-*`` headers are
      believed; empty trusts none. Behind a proxy, leaving it empty makes
      every request look like it came from the proxy, so per-client
      counts such as the login throttle's become one count for everybody.
      ``register_core``.
    - ``role_groups`` (``ROLE_GROUPS``): directory group → role names, e.g.
      ``"finance=admin|editor,staff=viewer"`` (or a JSON object).
      ``register_permissions``.
    - ``role_bootstrap`` (``ROLE_BOOTSTRAP``): subject → role names in the
      same form, for the first admin and for recovery. ``register_permissions``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    secret_key: str
    log_level: str = "INFO"
    settings_cipher_key: str = ""

    auth_adapter: str = "local"
    cors_allowed_origins: str = ""
    trusted_proxies: str = ""
    role_groups: str = ""
    role_bootstrap: str = ""
