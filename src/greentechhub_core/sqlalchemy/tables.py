"""sqlalchemy.tables — the gth_settings and gth_role_grants tables, defined
on a MetaData the service passes in so its own Alembic migrates them.

Core holds no data and owns no engine: these functions only add Table
definitions to the service's metadata. Calling one again on the same
metadata returns the table already there, so it's safe to call from both
the app and Alembic's env.py.
"""

import sqlalchemy as sa

SETTINGS_TABLE = "gth_settings"
ROLE_GRANTS_TABLE = "gth_role_grants"

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
