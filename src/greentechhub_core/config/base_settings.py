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
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    secret_key: str
    log_level: str = "INFO"
