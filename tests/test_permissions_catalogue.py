import dataclasses

import pytest

from greentechhub_core.permissions import Permission, Role, permission

# Permission — construction


def test_permission_constructs_from_valid_resource_action_string():
    assert Permission("portfolio.view") == "portfolio.view"


def test_permission_factory_builds_from_separate_parts():
    assert permission("portfolio", "view") == Permission("portfolio.view")


def test_permission_factory_returns_a_permission_instance():
    assert isinstance(permission("portfolio", "view"), Permission)


# Permission — validation


def test_permission_rejects_empty_string():
    with pytest.raises(ValueError):
        Permission("")


def test_permission_rejects_missing_dot():
    with pytest.raises(ValueError):
        Permission("portfolioview")


def test_permission_rejects_more_than_one_dot():
    with pytest.raises(ValueError):
        Permission("portfolio.view.extra")


def test_permission_rejects_empty_resource_segment():
    with pytest.raises(ValueError):
        Permission(".view")


def test_permission_rejects_empty_action_segment():
    with pytest.raises(ValueError):
        Permission("portfolio.")


def test_permission_rejects_disallowed_characters():
    with pytest.raises(ValueError):
        Permission("portfolio.view-all")


def test_permission_factory_rejects_embedded_dot_in_resource():
    with pytest.raises(ValueError):
        permission("portfolio.extra", "view")


# Permission — behaves like a str


def test_permission_equals_plain_string():
    assert Permission("portfolio.view") == "portfolio.view"


def test_permission_is_a_str_instance():
    assert isinstance(Permission("portfolio.view"), str)


def test_permission_usable_as_dict_key():
    perm = Permission("portfolio.view")
    lookup = {perm: "allowed"}
    assert lookup["portfolio.view"] == "allowed"


def test_permission_formats_like_its_string_value():
    perm = Permission("portfolio.view")
    assert f"{perm}" == "portfolio.view"


# Role


def test_role_construction_requires_keyword_args():
    Role(name="Trader", permissions={Permission("portfolio.view")})
    with pytest.raises(TypeError):
        Role("Trader", {Permission("portfolio.view")})


def test_role_permissions_accessible():
    role = Role(
        name="Trader",
        permissions={Permission("portfolio.view"), Permission("portfolio.edit")},
    )
    assert role.permissions == {Permission("portfolio.view"), Permission("portfolio.edit")}


def test_role_coerces_any_iterable_to_a_frozenset():
    role = Role(
        name="Trader", permissions=[Permission("portfolio.view"), Permission("portfolio.view")]
    )
    assert role.permissions == frozenset({Permission("portfolio.view")})


def test_role_coerces_plain_strings_into_validated_permissions():
    role = Role(name="Trader", permissions=["portfolio.view"])
    assert role.permissions == {Permission("portfolio.view")}


def test_role_construction_rejects_invalid_permission_strings():
    with pytest.raises(ValueError):
        Role(name="Trader", permissions=["not-a-permission"])


def test_role_is_frozen():
    role = Role(name="Trader", permissions={Permission("portfolio.view")})
    with pytest.raises(dataclasses.FrozenInstanceError):
        role.name = "Investor"
