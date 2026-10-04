import asyncio

import pytest

import greentechhub_core.settings as settings_pkg
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Settings,
    SettingScope,
    SettingsRegistry,
    SettingType,
)
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    DENSITY,
    LANDING_PAGE_KEY,
    MOTION,
    NUMBER_FORMAT,
    PAGE_SIZE,
    SELF_SIGNUP_KEY,
    SIDEBAR_DEFAULT,
    SITE_BANNER_KEY,
    SITE_BANNER_TONE_KEY,
    SITE_BANNER_TONES,
    THEME,
    TIME_FORMAT,
    TIMEZONE,
    USER_PREFERENCES,
    landing_page_setting,
    self_signup_setting,
    site_banner_settings,
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


# landing page

PAGES = {"/": "Dashboard", "/reports": "Reports"}


def test_landing_page_setting_has_the_documented_shape():
    setting = landing_page_setting(PAGES, default="/")
    assert setting.key == LANDING_PAGE_KEY == "ui.landing_page"
    assert setting.type is SettingType.CHOICE
    assert setting.scope is SettingScope.USER
    assert setting.group == "Navigation"
    assert setting.choices == (("/", "Dashboard"), ("/reports", "Reports"))
    assert setting.default == "/"
    assert (setting.label, setting.help_text) == (
        "Landing page",
        "The page you see after signing in.",
    )


def test_landing_page_setting_label_and_help_text_override():
    setting = landing_page_setting(PAGES, default="/reports", label="Home", help_text="")
    assert (setting.label, setting.help_text, setting.default) == ("Home", "", "/reports")


@pytest.mark.parametrize(
    "choices",
    [PAGES, [("/", "Dashboard"), ("/reports", "Reports")], ["/", "/reports"]],
)
def test_landing_page_setting_takes_every_choices_form(choices):
    assert landing_page_setting(choices, default="/").choice_values == ("/", "/reports")


@pytest.mark.parametrize(("choices", "default"), [(PAGES, "/admin"), ({}, "/")])
def test_landing_page_setting_rejects_a_default_outside_the_choices(choices, default):
    with pytest.raises(ValueError):
        landing_page_setting(choices, default=default)


def test_landing_page_setting_is_opt_in_and_registers_with_the_preferences():
    assert LANDING_PAGE_KEY not in {s.key for s in USER_PREFERENCES}
    registry = SettingsRegistry([*USER_PREFERENCES, landing_page_setting(PAGES, default="/")])
    assert registry.resolve(LANDING_PAGE_KEY) == "/"
    assert registry.resolve(LANDING_PAGE_KEY, user={LANDING_PAGE_KEY: "/reports"}) == "/reports"
    assert registry.resolve(LANDING_PAGE_KEY, user={LANDING_PAGE_KEY: "/gone"}) == "/"
    assert registry.coerce(LANDING_PAGE_KEY, "/reports") == "/reports"


# site_banner_settings


def test_site_banner_settings_have_the_documented_shape():
    banner, tone = site_banner_settings()
    assert (banner.key, tone.key) == (SITE_BANNER_KEY, SITE_BANNER_TONE_KEY)
    assert (SITE_BANNER_KEY, SITE_BANNER_TONE_KEY) == ("site.banner", "site.banner_tone")
    assert banner.type is SettingType.STR and banner.default == ""
    assert tone.type is SettingType.CHOICE and tone.default == "warn"
    assert banner.scope is SettingScope.APP and tone.scope is SettingScope.APP
    assert banner.group == tone.group == "Site"
    assert banner.edit_permission is None and tone.edit_permission is None
    # Exactly greentechhub-ui's gth_alert_banner tones.
    assert tone.choice_values == ("info", "warn", "bad", "good", "neutral")
    assert dict(tone.choices) == SITE_BANNER_TONES


def test_site_banner_settings_take_the_services_permission_and_group():
    banner, tone = site_banner_settings(edit_permission="settings.manage", group="App")
    assert banner.edit_permission == tone.edit_permission == "settings.manage"
    assert banner.group == tone.group == "App"


def test_site_banner_settings_are_opt_in_and_register_with_the_preferences():
    keys = {s.key for s in USER_PREFERENCES}
    assert SITE_BANNER_KEY not in keys and SITE_BANNER_TONE_KEY not in keys
    registry = SettingsRegistry([*USER_PREFERENCES, *site_banner_settings()])
    assert registry.resolve(SITE_BANNER_KEY) == ""  # no banner by default
    app = {SITE_BANNER_KEY: "Down for maintenance at 9pm", SITE_BANNER_TONE_KEY: "bad"}
    assert registry.resolve(SITE_BANNER_KEY, app=app) == "Down for maintenance at 9pm"
    assert registry.resolve(SITE_BANNER_TONE_KEY, app=app) == "bad"
    # A stored tone the banner can't show falls back to the default.
    assert registry.resolve(SITE_BANNER_TONE_KEY, app={SITE_BANNER_TONE_KEY: "shout"}) == "warn"


def test_site_banner_tone_accepts_only_the_banner_tones():
    _, tone = site_banner_settings()
    for value in SITE_BANNER_TONES:
        assert tone.coerce(value) == value
    with pytest.raises(ValueError):
        tone.validate("danger")  # a toast kind, not a banner tone
    banner, _ = site_banner_settings()
    assert banner.validate("") == ""  # empty means no banner


# self_signup_setting


def test_self_signup_setting_has_the_documented_shape():
    setting = self_signup_setting()
    assert setting.key == SELF_SIGNUP_KEY == "auth.self_signup"
    assert setting.type is SettingType.BOOL and setting.default is True
    assert setting.scope is SettingScope.APP
    assert setting.group == "Sign-up" and setting.label == "Allow sign-up"
    assert setting.edit_permission is None


def test_self_signup_setting_overrides():
    setting = self_signup_setting(default=False, edit_permission="settings.manage",
                                  group="Accounts", label="Open registration", help_text="")
    assert setting.default is False
    assert (setting.edit_permission, setting.group, setting.label, setting.help_text) == (
        "settings.manage", "Accounts", "Open registration", "")


def test_self_signup_setting_resolves_through_settings():
    store = InMemorySettingsStore()
    settings = Settings(SettingsRegistry([self_signup_setting()]), store)
    assert asyncio.run(settings.get(SELF_SIGNUP_KEY, None)) is True
    store.set_sync(SettingScope.APP, None, SELF_SIGNUP_KEY, False)
    assert asyncio.run(settings.get(SELF_SIGNUP_KEY, None)) is False
