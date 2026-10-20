"""users — user accounts, linked external sign-ins, and resolving either a
password or an Identity from another source to one account — see
docs/users.md.

A UserStore here (InMemoryUserStore) and in greentechhub_core.sqlalchemy
(SQLAlchemyUserStore).
"""

from greentechhub_core.users.model import (
    LOCAL_PROVIDER,
    LinkedIdentity,
    LinkExists,
    ProvisioningPolicy,
    Resolution,
    UserAccount,
    UserExists,
    account_identity,
    apply_changes,
    clean_display_name,
    new_account,
    normalize_email,
    normalize_username,
)
from greentechhub_core.users.resolve import (
    authenticate,
    authenticate_sync,
    resolve_account,
    resolve_account_sync,
    set_password,
    set_password_sync,
)
from greentechhub_core.users.store import InMemoryUserStore, UserStore

__all__ = [
    "LOCAL_PROVIDER",
    "InMemoryUserStore",
    "LinkExists",
    "LinkedIdentity",
    "ProvisioningPolicy",
    "Resolution",
    "UserAccount",
    "UserExists",
    "UserStore",
    "account_identity",
    "apply_changes",
    "authenticate",
    "authenticate_sync",
    "clean_display_name",
    "new_account",
    "normalize_email",
    "normalize_username",
    "resolve_account",
    "resolve_account_sync",
    "set_password",
    "set_password_sync",
]
