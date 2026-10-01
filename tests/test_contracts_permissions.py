import pytest

from greentechhub_core.contracts.permissions import GrantStoreContract, PermissionResolverContract
from greentechhub_core.identity.models import Identity
from greentechhub_core.permissions import InMemoryGrantStore, Permission, Role, RoleResolver

_ROLES = (
    Role(name="viewer", permissions={Permission("reports.view")}),
    Role(name="admin", permissions={Permission("reports.view"), Permission("settings.manage")}),
)


class TestInMemoryGrantStoreContract(GrantStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryGrantStore:
        return InMemoryGrantStore()


class TestRoleResolverContract(PermissionResolverContract):
    @pytest.fixture
    def resolver(self) -> RoleResolver:
        return RoleResolver(
            roles=_ROLES,
            group_roles={"staff": ["viewer"]},
            bootstrap={"root": ["admin"]},
            grants=InMemoryGrantStore({"granted-user": {"viewer"}}),
        )

    @pytest.fixture
    def granted_identity(self) -> Identity:
        return Identity(subject="granted-user", username="g", email=None, groups=[], claims={})
