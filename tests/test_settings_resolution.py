import pytest

from greentechhub_core.settings import (
    Setting,
    SettingScope,
    SettingType,
    env_var_name,
    read_env_overrides,
    resolve,
)

USER_SETTING = Setting(
    key="ui.page_size",
    type=SettingType.INT,
    default=25,
    scope=SettingScope.USER,
    label="Rows",
    min=5,
    max=200,
)
APP_SETTING = Setting(
    key="site.maintenance",
    type=SettingType.BOOL,
    default=False,
    scope=SettingScope.APP,
    label="Maintenance mode",
)
KEY = USER_SETTING.key


# order


def test_default_when_no_layer_has_a_value():
    assert resolve(USER_SETTING) == 25


def test_user_beats_app_beats_env_beats_default():
    user, app, env = {KEY: 10}, {KEY: 20}, {KEY: 30}
    assert resolve(USER_SETTING, user=user, app=app, env=env) == 10
    assert resolve(USER_SETTING, app=app, env=env) == 20
    assert resolve(USER_SETTING, env=env) == 30


def test_an_app_setting_ignores_user_values():
    key = APP_SETTING.key
    assert resolve(APP_SETTING, user={key: True}) is False
    assert resolve(APP_SETTING, user={key: True}, env={key: True}) is True
    assert resolve(APP_SETTING, app={key: False}, env={key: True}) is False


def test_an_invalid_stored_value_falls_through_to_the_next_layer():
    assert resolve(USER_SETTING, user={KEY: 1000}, app={KEY: "20"}, env={KEY: 30}) == 30
    assert resolve(USER_SETTING, user={KEY: None}) == 25


def test_other_keys_in_a_layer_are_ignored():
    assert resolve(USER_SETTING, user={"ui.theme": "dark"}) == 25


# env


def test_env_var_name():
    assert env_var_name("ui.page_size") == "SETTING_UI__PAGE_SIZE"
    assert env_var_name("theme", prefix="MYAPP_") == "MYAPP_THEME"


def test_read_env_overrides_coerces_present_vars_only():
    environ = {"SETTING_UI__PAGE_SIZE": "50", "SETTING_SITE__MAINTENANCE": "yes"}
    assert read_env_overrides([USER_SETTING, APP_SETTING], environ) == {
        KEY: 50,
        "site.maintenance": True,
    }
    assert read_env_overrides([USER_SETTING], {}) == {}


def test_read_env_overrides_honours_the_prefix():
    overrides = read_env_overrides([USER_SETTING], {"APP_UI__PAGE_SIZE": "50"}, prefix="APP_")
    assert overrides == {KEY: 50}


def test_read_env_overrides_raises_naming_the_env_var():
    with pytest.raises(ValueError, match="SETTING_UI__PAGE_SIZE: .*above the maximum"):
        read_env_overrides([USER_SETTING], {"SETTING_UI__PAGE_SIZE": "999"})


def test_read_env_overrides_defaults_to_os_environ(monkeypatch):
    monkeypatch.setenv("SETTING_UI__PAGE_SIZE", "40")
    assert read_env_overrides([USER_SETTING]) == {KEY: 40}
