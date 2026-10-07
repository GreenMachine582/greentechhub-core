"""config.readers (setting_value, read_list_setting, read_str_setting) and
permissions.role_map (parse_role_map, read_role_map): the adapter settings
read the same way in every adapter."""

from types import SimpleNamespace as NS

import pytest

from greentechhub_core.config import (
    GTHBaseSettings,
    read_list_setting,
    read_str_setting,
    setting_value,
)
from greentechhub_core.permissions import parse_role_map, read_role_map

# setting_value / read_*_setting


def test_the_screaming_case_attribute_wins_when_set():
    # a service that set AUTH_ADAPTER itself isn't overridden by the
    # lowercase field's non-empty default
    settings = NS(auth_adapter="local", AUTH_ADAPTER="forward_auth")
    assert setting_value(settings, "AUTH_ADAPTER") == "forward_auth"


def test_the_lowercase_field_is_the_fallback():
    assert setting_value(NS(auth_adapter="local", AUTH_ADAPTER=""), "AUTH_ADAPTER") == "local"
    assert setting_value(NS(trusted_proxies="10.0.0.1"), "TRUSTED_PROXIES") == "10.0.0.1"
    assert setting_value(NS(), "TRUSTED_PROXIES") is None


def test_gthbasesettings_fields_are_read_from_the_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1, 10.0.0.2")
    monkeypatch.setenv("AUTH_ADAPTER", "forward_auth")
    settings = GTHBaseSettings(_env_file=None)
    assert read_list_setting(settings, "TRUSTED_PROXIES") == ["10.0.0.1", "10.0.0.2"]
    assert read_str_setting(settings, "AUTH_ADAPTER", "local") == "forward_auth"


@pytest.mark.parametrize("value, expected", [
    ("a, ,b,", ["a", "b"]),
    (["a", 2], ["a", "2"]),
    (("x",), ["x"]),
    ("", []),
    (None, []),
    (42, []),
])
def test_read_list_setting_shapes(value, expected):
    assert read_list_setting(NS(CORS_ALLOWED_ORIGINS=value), "CORS_ALLOWED_ORIGINS") == expected


def test_read_str_setting_defaults_when_empty():
    assert read_str_setting(NS(AUTH_ADAPTER=""), "AUTH_ADAPTER", "local") == "local"
    assert read_str_setting(NS(), "AUTH_ADAPTER", "local") == "local"


# parse_role_map / read_role_map


@pytest.mark.parametrize("value", [
    "alice=admin|editor,bob=viewer",
    " alice = admin | editor , bob=viewer ",
    '{"alice": ["admin", "editor"], "bob": "viewer"}',
    {"alice": ["admin", "editor"], "bob": ["viewer"]},
    {"alice": "admin,editor", "bob": "viewer"},
])
def test_parse_role_map_accepts_every_form(value):
    expected = {"alice": ["admin", "editor"], "bob": ["viewer"]}
    assert parse_role_map(value, "ROLE_BOOTSTRAP") == expected


@pytest.mark.parametrize("value", [None, "", {}])
def test_parse_role_map_treats_missing_as_empty(value):
    assert parse_role_map(value, "ROLE_BOOTSTRAP") == {}


@pytest.mark.parametrize("value", ["alice", "=admin", "{not json", "[1]", '["alice"]'])
def test_parse_role_map_rejects_malformed_values(value):
    with pytest.raises(ValueError, match="ROLE_BOOTSTRAP"):
        parse_role_map(value, "ROLE_BOOTSTRAP")


def test_read_role_map_reads_either_name():
    assert read_role_map(NS(ROLE_BOOTSTRAP="alice=admin"), "ROLE_BOOTSTRAP") == {"alice": ["admin"]}
    assert read_role_map(NS(role_groups="staff=viewer"), "ROLE_GROUPS") == {"staff": ["viewer"]}
    assert read_role_map(NS(), "ROLE_GROUPS") == {}
