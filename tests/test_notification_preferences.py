import asyncio

import pytest

from greentechhub_core.identity.models import Identity
from greentechhub_core.notifications import (
    DELIVERY_CHOICES,
    channels_for,
    channels_for_sync,
    delivery_channels,
    notification_preferences,
    preference_key,
)
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Settings,
    SettingScope,
    SettingsRegistry,
    SettingType,
)

ALICE = Identity(subject="alice", username="alice", email=None, groups=[], claims={})


def test_one_user_choice_per_category():
    sync, deals = notification_preferences({"sync": "Sync results", "deals": "Deals found"})
    assert (sync.key, deals.key) == ("notify.sync", "notify.deals") == (
        preference_key("sync"), preference_key("deals"))
    for setting in (sync, deals):
        assert setting.type is SettingType.CHOICE and setting.scope is SettingScope.USER
        assert setting.choice_values == ("in_app", "email", "both", "off")
        assert setting.default == "in_app" and setting.group == "Notifications"
    assert (sync.label, deals.label) == ("Sync results", "Deals found")


def test_categories_as_pairs_or_bare_names():
    pairs = notification_preferences([("sync", "Syncs")])
    bare = notification_preferences(["price_alert"])
    assert pairs[0].label == "Syncs"
    assert (bare[0].key, bare[0].label) == ("notify.price_alert", "Price alert")


def test_options():
    (setting,) = notification_preferences(["sync"], default="both", group="Alerts",
                                          help_text="How we tell you.")
    assert (setting.default, setting.group) == ("both", "Alerts")
    assert setting.help_text == "How we tell you."


@pytest.mark.parametrize(("categories", "kwargs"), [
    ([], {}),
    (["sync"], {"default": "sms"}),
    (["Deal Found"], {}),  # not a key segment
])
def test_rejects_bad_input(categories, kwargs):
    with pytest.raises(ValueError):
        notification_preferences(categories, **kwargs)


def test_delivery_channels():
    assert delivery_channels("in_app") == {"in_app"}
    assert delivery_channels("email") == {"email"}
    assert delivery_channels("both") == {"in_app", "email"}
    assert delivery_channels("off") == frozenset()
    assert set(DELIVERY_CHOICES) == {"in_app", "email", "both", "off"}
    with pytest.raises(ValueError):
        delivery_channels("pigeon")


def _settings():
    store = InMemorySettingsStore()
    registry = SettingsRegistry([*notification_preferences(["sync"], default="both")])
    return Settings(registry, store), store


def test_channels_follow_the_default_then_the_users_choice():
    settings, store = _settings()
    assert channels_for_sync(settings, ALICE, "sync") == {"in_app", "email"}
    store.set_sync(SettingScope.USER, "alice", "notify.sync", "off")
    assert channels_for_sync(settings, ALICE, "sync") == frozenset()
    store.set_sync(SettingScope.USER, "alice", "notify.sync", "email")
    assert channels_for_sync(settings, ALICE, "sync") == {"email"}
    assert channels_for_sync(settings, None, "sync") == {"in_app", "email"}  # no user: the default


def test_an_unregistered_category_goes_in_app():
    settings, _ = _settings()
    assert channels_for_sync(settings, ALICE, "deals") == {"in_app"}


def test_async_and_sync_agree():
    settings, store = _settings()
    store.set_sync(SettingScope.USER, "alice", "notify.sync", "email")

    async def run():
        return [await channels_for(settings, ALICE, c) for c in ("sync", "deals")]

    assert asyncio.run(run()) == [channels_for_sync(settings, ALICE, c) for c in ("sync", "deals")]
