import pytest

from greentechhub_core.settings import Setting, SettingScope, SettingsRegistry, SettingType

THEME = Setting(
    key="ui.theme",
    type=SettingType.CHOICE,
    default="system",
    scope=SettingScope.USER,
    label="Theme",
    choices=["light", "dark", "system"],
)
PAGE_SIZE = Setting(
    key="ui.page_size",
    type=SettingType.INT,
    default=25,
    scope=SettingScope.USER,
    label="Rows",
    min=5,
    max=200,
)
BANNER = Setting(
    key="site.banner",
    type=SettingType.STR,
    default="",
    scope=SettingScope.APP,
    label="Banner",
    edit_permission="settings.manage",
)


def test_starts_empty():
    assert len(SettingsRegistry()) == 0


def test_registers_and_looks_up_in_registration_order():
    registry = SettingsRegistry([THEME])
    registry.register(PAGE_SIZE, BANNER)
    assert list(registry) == [THEME, PAGE_SIZE, BANNER]
    assert registry.get("ui.page_size") is PAGE_SIZE
    assert "site.banner" in registry
    assert "nope" not in registry


def test_duplicate_keys_are_rejected():
    registry = SettingsRegistry([THEME])
    with pytest.raises(ValueError, match="duplicate setting key 'ui.theme'"):
        registry.register(THEME)


def test_unknown_keys_raise_key_error():
    with pytest.raises(KeyError, match="unknown setting 'nope'"):
        SettingsRegistry().get("nope")


def test_for_scope_filters():
    registry = SettingsRegistry([THEME, BANNER, PAGE_SIZE])
    assert registry.for_scope(SettingScope.USER) == (THEME, PAGE_SIZE)
    assert registry.for_scope("app") == (BANNER,)


def test_validate_and_coerce_by_key():
    registry = SettingsRegistry([PAGE_SIZE])
    assert registry.validate("ui.page_size", 50) == 50
    assert registry.coerce("ui.page_size", "50") == 50
    with pytest.raises(ValueError):
        registry.coerce("ui.page_size", "1")
    with pytest.raises(KeyError):
        registry.coerce("nope", "1")


def test_env_overrides_reads_every_registered_setting():
    registry = SettingsRegistry([THEME, PAGE_SIZE, BANNER])
    environ = {"SETTING_UI__PAGE_SIZE": "50", "SETTING_SITE__BANNER": "Down at 5pm", "OTHER": "x"}
    assert registry.env_overrides(environ) == {"ui.page_size": 50, "site.banner": "Down at 5pm"}


def test_resolve_all_covers_every_setting_or_one_scope():
    registry = SettingsRegistry([THEME, PAGE_SIZE, BANNER])
    assert registry.resolve_all(user={"ui.theme": "dark"}, app={"site.banner": "hi"}) == {
        "ui.theme": "dark",
        "ui.page_size": 25,
        "site.banner": "hi",
    }
    assert registry.resolve_all(scope=SettingScope.APP) == {"site.banner": ""}


def test_resolve_all_ignores_unregistered_keys():
    registry = SettingsRegistry([THEME])
    assert registry.resolve_all(user={"ui.theme": "dark", "gone": 1}) == {"ui.theme": "dark"}


def test_resolve_one_key():
    registry = SettingsRegistry([PAGE_SIZE])
    assert registry.resolve("ui.page_size", app={"ui.page_size": 10}) == 10
