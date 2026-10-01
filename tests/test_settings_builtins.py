import pytest

import greentechhub_core.settings as settings_pkg
from greentechhub_core.settings import SettingScope, SettingsRegistry, SettingType
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    DENSITY,
    MOTION,
    NUMBER_FORMAT,
    PAGE_SIZE,
    SIDEBAR_DEFAULT,
    THEME,
    TIME_FORMAT,
    TIMEZONE,
    USER_PREFERENCES,
)


def test_user_preferences_are_the_shared_keys():
    assert [s.key for s in USER_PREFERENCES] == [
        "ui.theme",
        "locale.timezone",
        "locale.date_format",
        "ui.page_size",
        "ui.density",
        "ui.motion",
        "ui.sidebar_default",
        "locale.number_format",
        "locale.time_format",
    ]
    assert USER_PREFERENCES == (
        THEME,
        TIMEZONE,
        DATE_FORMAT,
        PAGE_SIZE,
        DENSITY,
        MOTION,
        SIDEBAR_DEFAULT,
        NUMBER_FORMAT,
        TIME_FORMAT,
    )
    assert all(s.scope is SettingScope.USER for s in USER_PREFERENCES)


def test_user_preference_keys_are_unique():
    keys = [s.key for s in USER_PREFERENCES]
    assert len(keys) == len(set(keys))


def test_nothing_is_registered_on_import():
    assert len(SettingsRegistry()) == 0
    assert "builtins" not in settings_pkg.__all__


def test_a_service_opts_in_by_passing_them_to_its_registry():
    registry = SettingsRegistry(USER_PREFERENCES)
    assert registry.resolve_all() == {
        "ui.theme": "system",
        "locale.timezone": "UTC",
        "locale.date_format": "iso",
        "ui.page_size": 25,
        "ui.density": "comfortable",
        "ui.motion": "system",
        "ui.sidebar_default": "expanded",
        "locale.number_format": "comma_dot",
        "locale.time_format": "24h",
    }


def test_a_service_can_register_a_subset():
    registry = SettingsRegistry([DENSITY, MOTION])
    assert registry.resolve_all() == {"ui.density": "comfortable", "ui.motion": "system"}


def test_timezone_always_offers_utc():
    assert "UTC" in TIMEZONE.choice_values
    assert TIMEZONE.coerce("UTC") == "UTC"


# The values below are the docs/settings.md table; ui keys its behaviour on them.
@pytest.mark.parametrize(
    ("setting", "key", "values", "default", "group"),
    [
        (DENSITY, "ui.density", ("comfortable", "compact"), "comfortable", "Appearance"),
        (MOTION, "ui.motion", ("system", "reduce", "full"), "system", "Appearance"),
        (SIDEBAR_DEFAULT, "ui.sidebar_default", ("expanded", "rail"), "expanded", "Appearance"),
        (
            NUMBER_FORMAT,
            "locale.number_format",
            ("comma_dot", "dot_comma", "space_comma"),
            "comma_dot",
            "Locale",
        ),
        (TIME_FORMAT, "locale.time_format", ("24h", "12h"), "24h", "Locale"),
    ],
)
def test_display_builtins_match_the_documented_shape(setting, key, values, default, group):
    assert setting.key == key
    assert setting.type is SettingType.CHOICE
    assert setting.scope is SettingScope.USER
    assert setting.choice_values == values
    assert setting.default == default
    assert setting.group == group
    for value in values:
        assert setting.coerce(value) == value
    with pytest.raises(ValueError):
        setting.validate("not-a-choice")
