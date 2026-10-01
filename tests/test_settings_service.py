import asyncio

import pytest

from greentechhub_core.identity.models import Identity
from greentechhub_core.permissions import Permission, Role, RoleResolver
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Setting,
    SettingPermissionError,
    Settings,
    SettingScope,
    SettingsRegistry,
    SettingType,
)
from greentechhub_core.settings.builtins import USER_PREFERENCES

MANAGE = Permission("settings.manage")
BANNER = Setting(
    key="site.banner",
    type=SettingType.STR,
    default="",
    scope=SettingScope.APP,
    label="Banner",
    edit_permission=MANAGE,
)
MAINTENANCE = Setting(
    key="site.maintenance",
    type=SettingType.BOOL,
    default=False,
    scope=SettingScope.APP,
    label="Maintenance",
)
ALICE = Identity(subject="alice", username="alice", email=None, groups=[], claims={})
BOB = Identity(subject="bob", username="bob", email=None, groups=["admins"], claims={})
ADMIN_GRANTED = RoleResolver(
    roles=[Role(name="admin", permissions={MANAGE})], group_roles={"admins": ["admin"]}
).granted_sync(BOB)


def _settings(env=None) -> Settings:
    registry = SettingsRegistry([*USER_PREFERENCES, BANNER, MAINTENANCE])
    return Settings(registry, InMemorySettingsStore(), env=env or {})


# reads


def test_effective_starts_at_the_defaults():
    assert _settings().effective_sync(ALICE) == {
        "ui.theme": "system",
        "locale.timezone": "UTC",
        "locale.date_format": "iso",
        "ui.page_size": 25,
        "ui.density": "comfortable",
        "ui.motion": "system",
        "ui.sidebar_default": "expanded",
        "locale.number_format": "comma_dot",
        "locale.time_format": "24h",
        "site.banner": "",
        "site.maintenance": False,
    }


def test_user_value_beats_app_value_beats_env():
    settings = _settings(env={"ui.page_size": 30})
    assert settings.get_sync("ui.page_size", ALICE) == 30
    settings.set_app_sync("ui.page_size", 40, granted=())
    assert settings.get_sync("ui.page_size", ALICE) == 40
    settings.set_user_sync(ALICE, "ui.page_size", 50)
    assert settings.get_sync("ui.page_size", ALICE) == 50
    assert settings.get_sync("ui.page_size", BOB) == 40


def test_anonymous_reads_skip_the_user_layer():
    settings = _settings()
    settings.set_user_sync(ALICE, "ui.theme", "dark")
    assert settings.get_sync("ui.theme") == "system"
    assert settings.effective_sync(None)["ui.theme"] == "system"


def test_env_defaults_to_the_registrys_env_overrides(monkeypatch):
    monkeypatch.setenv("SETTING_UI__PAGE_SIZE", "60")
    registry = SettingsRegistry(USER_PREFERENCES)
    assert Settings(registry, InMemorySettingsStore()).get_sync("ui.page_size") == 60


def test_a_malformed_env_override_fails_at_construction(monkeypatch):
    monkeypatch.setenv("SETTING_UI__PAGE_SIZE", "lots")
    with pytest.raises(ValueError, match="SETTING_UI__PAGE_SIZE"):
        Settings(SettingsRegistry(USER_PREFERENCES), InMemorySettingsStore())


def test_env_prefix_is_honoured(monkeypatch):
    monkeypatch.setenv("MYAPP_UI__THEME", "dark")
    settings = Settings(
        SettingsRegistry(USER_PREFERENCES), InMemorySettingsStore(), env_prefix="MYAPP_"
    )
    assert settings.get_sync("ui.theme") == "dark"


def test_unknown_key_raises_key_error():
    with pytest.raises(KeyError):
        _settings().get_sync("nope")


# user writes


def test_set_user_validates():
    settings = _settings()
    with pytest.raises(ValueError):
        settings.set_user_sync(ALICE, "ui.theme", "purple")
    with pytest.raises(ValueError):
        settings.set_user_sync(ALICE, "ui.page_size", "50")


def test_set_user_on_an_app_setting_raises():
    with pytest.raises(ValueError, match="app-scoped"):
        _settings().set_user_sync(ALICE, "site.banner", "hi")


def test_anonymous_cannot_set_preferences():
    with pytest.raises(SettingPermissionError) as info:
        _settings().set_user_sync(None, "ui.theme", "dark")
    assert info.value.permission is None
    assert isinstance(info.value, PermissionError)


def test_reset_user_falls_back_to_the_app_value():
    settings = _settings()
    settings.set_app_sync("ui.theme", "light", granted=())
    settings.set_user_sync(ALICE, "ui.theme", "dark")
    settings.reset_user_sync(ALICE, "ui.theme")
    assert settings.get_sync("ui.theme", ALICE) == "light"


# app writes


def test_set_app_needs_the_edit_permission():
    settings = _settings()
    with pytest.raises(SettingPermissionError) as info:
        settings.set_app_sync("site.banner", "hi", granted=frozenset())
    assert info.value.permission == "settings.manage"
    settings.set_app_sync("site.banner", "hi", granted=ADMIN_GRANTED)
    assert settings.get_sync("site.banner") == "hi"


def test_set_app_without_an_edit_permission_is_left_to_the_caller():
    settings = _settings()
    settings.set_app_sync("site.maintenance", True, granted=())
    assert settings.get_sync("site.maintenance") is True


def test_set_app_validates():
    with pytest.raises(ValueError):
        _settings().set_app_sync("site.maintenance", "yes", granted=())


def test_reset_app_needs_the_permission_and_falls_back_to_env():
    settings = _settings(env={"site.banner": "from env"})
    settings.set_app_sync("site.banner", "hi", granted=ADMIN_GRANTED)
    with pytest.raises(SettingPermissionError):
        settings.reset_app_sync("site.banner", granted=())
    settings.reset_app_sync("site.banner", granted=ADMIN_GRANTED)
    assert settings.get_sync("site.banner") == "from env"


def test_a_stale_stored_value_falls_through():
    settings = _settings()
    settings.store.set_sync(SettingScope.USER, "alice", "ui.theme", "removed-theme")
    assert settings.get_sync("ui.theme", ALICE) == "system"


# async


def test_async_methods_match_the_sync_ones():
    settings = _settings()

    async def exercise() -> None:
        await settings.set_user(ALICE, "ui.theme", "dark")
        await settings.set_app("site.banner", "hi", granted=ADMIN_GRANTED)
        assert await settings.get("ui.theme", ALICE) == "dark"
        assert await settings.effective(ALICE) == settings.effective_sync(ALICE)
        await settings.reset_user(ALICE, "ui.theme")
        await settings.reset_app("site.banner", granted=ADMIN_GRANTED)
        with pytest.raises(SettingPermissionError):
            await settings.set_app("site.banner", "x", granted=())

    asyncio.run(exercise())
    assert settings.get_sync("ui.theme", ALICE) == "system"
    assert settings.get_sync("site.banner") == ""
