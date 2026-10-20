"""greentechhub_core.sqlalchemy — SQLAlchemy-backed SettingsStore,
GrantStore, AttemptStore, NotificationStore, TokenStore, ApiTokenStore, AuditStore and UserStore
(docs/settings.md#storage-tables-shipped-sqlalchemy-extra), and
filtering, sorting and paging helpers for a service's own selects (docs/query.md#sqlalchemy),
behind the optional `[sqlalchemy]` extra.

Importing this package without SQLAlchemy installed raises ImportError
naming the extra. Nothing else in core imports it, so core itself keeps no
required SQLAlchemy dependency.

The one place in core that joins top-level modules (settings/,
permissions/, security/, notifications/, audit/ and users/) on purpose, the way
contracts/ does: it implements their protocols over the service's own
database.
"""

try:
    import sqlalchemy  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "greentechhub_core.sqlalchemy needs SQLAlchemy: pip install 'greentechhub-core[sqlalchemy]'"
    ) from exc

from greentechhub_core.sqlalchemy.api_tokens import SQLAlchemyApiTokenStore
from greentechhub_core.sqlalchemy.audit import SQLAlchemyAuditStore
from greentechhub_core.sqlalchemy.database import Database
from greentechhub_core.sqlalchemy.grants import SQLAlchemyGrantStore
from greentechhub_core.sqlalchemy.notifications import SQLAlchemyNotificationStore
from greentechhub_core.sqlalchemy.one_time import SQLAlchemyTokenStore
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
    API_TOKENS_TABLE,
    AUDIT_LOG_TABLE,
    LOGIN_ATTEMPTS_TABLE,
    NOTIFICATIONS_TABLE,
    ONE_TIME_TOKENS_TABLE,
    ROLE_GRANTS_TABLE,
    SETTINGS_TABLE,
    USER_IDENTITIES_TABLE,
    USERS_TABLE,
    api_tokens_table,
    audit_log_table,
    login_attempts_table,
    notifications_table,
    one_time_tokens_table,
    role_grants_table,
    settings_table,
    user_identities_table,
    users_table,
)
from greentechhub_core.sqlalchemy.throttle import SQLAlchemyAttemptStore
from greentechhub_core.sqlalchemy.users import SQLAlchemyUserStore

__all__ = [
    "API_TOKENS_TABLE",
    "AUDIT_LOG_TABLE",
    "Database",
    "LOGIN_ATTEMPTS_TABLE",
    "NOTIFICATIONS_TABLE",
    "ONE_TIME_TOKENS_TABLE",
    "ROLE_GRANTS_TABLE",
    "SETTINGS_TABLE",
    "SQLAlchemyApiTokenStore",
    "SQLAlchemyAuditStore",
    "SQLAlchemyAttemptStore",
    "SQLAlchemyGrantStore",
    "SQLAlchemyNotificationStore",
    "SQLAlchemySettingsStore",
    "SQLAlchemyTokenStore",
    "SQLAlchemyUserStore",
    "USERS_TABLE",
    "USER_IDENTITIES_TABLE",
    "order_by",
    "page",
    "page_sync",
    "paginate",
    "paginate_sync",
    "api_tokens_table",
    "audit_log_table",
    "login_attempts_table",
    "notifications_table",
    "one_time_tokens_table",
    "role_grants_table",
    "settings_table",
    "user_identities_table",
    "users_table",
    "where",
]
