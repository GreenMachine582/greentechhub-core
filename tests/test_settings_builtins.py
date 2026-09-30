import greentechhub_core.settings as settings_pkg
from greentechhub_core.settings import SettingScope, SettingsRegistry
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    PAGE_SIZE,
    THEME,
    TIMEZONE,
    USER_PREFERENCES,
)


def test_user_preferences_are_the_four_shared_keys():
    assert [s.key for s in USER_PREFERENCES] == [
        "ui.theme",
        "locale.timezone",
        "locale.date_format",
        "ui.page_size",
    ]
    assert USER_PREFERENCES == (THEME, TIMEZONE, DATE_FORMAT, PAGE_SIZE)
    assert all(s.scope is SettingScope.USER for s in USER_PREFERENCES)


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
    }


def test_timezone_always_offers_utc():
    assert "UTC" in TIMEZONE.choice_values
    assert TIMEZONE.coerce("UTC") == "UTC"
