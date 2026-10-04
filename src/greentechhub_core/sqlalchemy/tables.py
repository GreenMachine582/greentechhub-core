"""sqlalchemy.tables — the gth_settings, gth_role_grants and gth_login_attempts tables, defined
on a MetaData the service passes in so its own Alembic migrates them.

Core holds no data and owns no engine: these functions only add Table
definitions to the service's metadata. Calling one again on the same
metadata returns the table already there, so it's safe to call from both
the app and Alembic's env.py.
"""

import sqlalchemy as sa

SETTINGS_TABLE = "gth_settings"
ROLE_GRANTS_TABLE = "gth_role_grants"
LOGIN_ATTEMPTS_TABLE = "gth_login_attempts"

APP_SUBJECT = ""
"""The `subject` stored on APP rows. The column is part of the primary key,
so it can't be NULL; an empty string never clashes with a real user, since
check_owner rejects an empty USER subject."""


def settings_table(metadata: sa.MetaData) -> sa.Table:
    """gth_settings: one row per stored value.

    scope    "app" or "user"
    subject  the user's subject, or "" for app values
    key      the setting key
    value    the typed value (bool, int or str) as JSON
    updated_at
    """
    if SETTINGS_TABLE in metadata.tables:
        return metadata.tables[SETTINGS_TABLE]
    return sa.Table(
        SETTINGS_TABLE,
        metadata,
        sa.Column("scope", sa.String(16), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def role_grants_table(metadata: sa.MetaData) -> sa.Table:
    """gth_role_grants: one row per (subject, role name) grant."""
    if ROLE_GRANTS_TABLE in metadata.tables:
        return metadata.tables[ROLE_GRANTS_TABLE]
    return sa.Table(
        ROLE_GRANTS_TABLE,
        metadata,
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("role", sa.String(255), primary_key=True),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def login_attempts_table(metadata: sa.MetaData) -> sa.Table:
    """gth_login_attempts: one row per throttled key (security.throttle).

    key           e.g. "account:alice" or "client:203.0.113.7"
    failures      failures counted in the current window
    window_start  when the current window began
    locked_until  when a lockout ends, or NULL
    """
    if LOGIN_ATTEMPTS_TABLE in metadata.tables:
        return metadata.tables[LOGIN_ATTEMPTS_TABLE]
    return sa.Table(
        LOGIN_ATTEMPTS_TABLE,
        metadata,
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("failures", sa.Integer, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
