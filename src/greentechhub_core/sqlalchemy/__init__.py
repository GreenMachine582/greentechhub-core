"""greentechhub_core.sqlalchemy — SQLAlchemy-backed SettingsStore,
GrantStore and AttemptStore (docs/settings.md#storage-tables-shipped-sqlalchemy-extra), and
filtering, sorting and paging helpers for a service's own selects (docs/query.md#sqlalchemy),
behind the optional `[sqlalchemy]` extra.

Importing this package without SQLAlchemy installed raises ImportError
naming the extra. Nothing else in core imports it, so core itself keeps no
required SQLAlchemy dependency.

The one place in core that joins top-level modules (settings/,
permissions/ and security/) on purpose, the way contracts/ does: it implements their
protocols over the service's own database.
"""

try:
    import sqlalchemy  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "greentechhub_core.sqlalchemy needs SQLAlchemy: pip install 'greentechhub-core[sqlalchemy]'"
    ) from exc

from greentechhub_core.sqlalchemy.grants import SQLAlchemyGrantStore
from greentechhub_core.sqlalchemy.query import (
    order_by,
    page,
    page_sync,
    paginate,
    paginate_sync,
    where,
)
from greentechhub_core.sqlalchemy.settings import SQLAlchemySettingsStore
from greentechhub_core.sqlalchemy.tables import (
    LOGIN_ATTEMPTS_TABLE,
    ROLE_GRANTS_TABLE,
    SETTINGS_TABLE,
    login_attempts_table,
    role_grants_table,
    settings_table,
)
from greentechhub_core.sqlalchemy.throttle import SQLAlchemyAttemptStore

__all__ = [
    "LOGIN_ATTEMPTS_TABLE",
    "ROLE_GRANTS_TABLE",
    "SETTINGS_TABLE",
    "SQLAlchemyAttemptStore",
    "SQLAlchemyGrantStore",
    "SQLAlchemySettingsStore",
    "order_by",
    "page",
    "page_sync",
    "paginate",
    "paginate_sync",
    "login_attempts_table",
    "role_grants_table",
    "settings_table",
    "where",
]
