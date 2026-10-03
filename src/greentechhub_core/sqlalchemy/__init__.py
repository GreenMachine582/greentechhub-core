"""greentechhub_core.sqlalchemy — SQLAlchemy-backed SettingsStore and
GrantStore (docs/settings.md#storage-tables-shipped-sqlalchemy-extra), and
paging/sorting helpers for a service's own selects (docs/query.md#sqlalchemy),
behind the optional `[sqlalchemy]` extra.

Importing this package without SQLAlchemy installed raises ImportError
naming the extra. Nothing else in core imports it, so core itself keeps no
required SQLAlchemy dependency.

The one place in core that joins top-level modules (settings/ and
permissions/) on purpose, the way contracts/ does: it implements their
protocols over the service's own database.
"""

try:
    import sqlalchemy  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "greentechhub_core.sqlalchemy needs SQLAlchemy: pip install 'greentechhub-core[sqlalchemy]'"
    ) from exc

from greentechhub_core.sqlalchemy.grants import SQLAlchemyGrantStore
from greentechhub_core.sqlalchemy.query import order_by, paginate, paginate_sync
from greentechhub_core.sqlalchemy.settings import SQLAlchemySettingsStore
from greentechhub_core.sqlalchemy.tables import (
    ROLE_GRANTS_TABLE,
    SETTINGS_TABLE,
    role_grants_table,
    settings_table,
)

__all__ = [
    "ROLE_GRANTS_TABLE",
    "SETTINGS_TABLE",
    "SQLAlchemyGrantStore",
    "SQLAlchemySettingsStore",
    "order_by",
    "paginate",
    "paginate_sync",
    "role_grants_table",
    "settings_table",
]
