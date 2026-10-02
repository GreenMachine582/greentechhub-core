import asyncio
import pickle

import pytest

from greentechhub_core.identity.models import Identity
from greentechhub_core.permissions import Permission
from greentechhub_core.settings import (
    SECRET_SET,
    InMemorySettingsStore,
    JsonFileSettingsStore,
    SecretDecryptError,
    Setting,
    SettingPermissionError,
    Settings,
    SettingScope,
    SettingsRegistry,
    SettingType,
    read_env_overrides,
)
from greentechhub_core.settings.crypto import FernetCipher

MANAGE = Permission("settings.manage")
PASSWORD = Setting(
    key="email.app_password",
    type=SettingType.STR,
    default="",
    scope=SettingScope.USER,
    label="App password",
    secret=True,
)
API_TOKEN = Setting(
    key="billing.api_token",
    type=SettingType.STR,
    default="",
    scope=SettingScope.APP,
    label="API token",
    secret=True,
    edit_permission=MANAGE,
)
ADDRESS = Setting(
    key="email.address",
    type=SettingType.STR,
    default="",
    scope=SettingScope.USER,
    label="Address",
)
ALICE = Identity(subject="alice", username="alice", email=None, groups=[], claims={})
BOB = Identity(subject="bob", username="bob", email=None, groups=[], claims={})
KEY = FernetCipher.generate_key()


def _settings(store=None, cipher=None) -> Settings:
    registry = SettingsRegistry([PASSWORD, API_TOKEN, ADDRESS])
    return Settings(
        registry, store or InMemorySettingsStore(), env={}, cipher=cipher or FernetCipher(KEY)
    )


# definition


@pytest.mark.parametrize(
    ("type_", "default", "extra"),
    [
        (SettingType.BOOL, False, {}),
        (SettingType.INT, 0, {}),
        (SettingType.CHOICE, "a", {"choices": ["a", "b"]}),
    ],
)
def test_only_a_str_setting_can_be_secret(type_, default, extra):
    with pytest.raises(ValueError, match="only a str setting can be secret"):
        Setting(
            key="x.y",
            type=type_,
            default=default,
            scope=SettingScope.APP,
            label="X",
            secret=True,
            **extra,
        )


def test_a_secret_cant_have_a_default():
    with pytest.raises(ValueError, match="default must be ''"):
        Setting(
            key="x.y",
            type=SettingType.STR,
            default="hunter2",
            scope=SettingScope.APP,
            label="X",
            secret=True,
        )


def test_settings_are_not_secret_by_default():
    assert ADDRESS.secret is False


# construction


def test_a_secret_setting_without_a_cipher_fails_fast():
    with pytest.raises(ValueError, match="email.app_password"):
        Settings(SettingsRegistry([PASSWORD, ADDRESS]), InMemorySettingsStore(), env={})


def test_no_secrets_needs_no_cipher():
    Settings(SettingsRegistry([ADDRESS]), InMemorySettingsStore(), env={})


def test_a_secret_cant_come_from_an_env_var():
    with pytest.raises(ValueError, match="SETTING_EMAIL__APP_PASSWORD"):
        read_env_overrides([PASSWORD], {"SETTING_EMAIL__APP_PASSWORD": "hunter2"})
    with pytest.raises(ValueError, match="SETTING_EMAIL__APP_PASSWORD"):
        SettingsRegistry([PASSWORD]).env_overrides({"SETTING_EMAIL__APP_PASSWORD": "x"})


def test_a_secret_cant_come_from_an_explicit_env_mapping():
    with pytest.raises(ValueError, match="can't come from env"):
        Settings(
            SettingsRegistry([PASSWORD]),
            InMemorySettingsStore(),
            env={"email.app_password": "hunter2"},
            cipher=FernetCipher(KEY),
        )


def test_env_overrides_still_apply_to_other_settings():
    assert read_env_overrides([PASSWORD, ADDRESS], {"SETTING_EMAIL__ADDRESS": "a@b.c"}) == {
        "email.address": "a@b.c"
    }


# round trip and storage


def test_user_secret_round_trips_and_is_per_user():
    settings = _settings()
    settings.set_user_sync(ALICE, "email.app_password", "alice-pw")
    settings.set_user_sync(BOB, "email.app_password", "bob-pw")
    assert settings.get_secret_sync("email.app_password", ALICE) == "alice-pw"
    assert settings.get_secret_sync("email.app_password", BOB) == "bob-pw"


def test_async_round_trip():
    async def run():
        settings = _settings()
        await settings.set_user(ALICE, "email.app_password", "alice-pw")
        await settings.set_app("billing.api_token", "tok", granted={MANAGE})
        return (
            await settings.get_secret("email.app_password", ALICE),
            await settings.get_secret("billing.api_token"),
        )

    assert asyncio.run(run()) == ("alice-pw", "tok")


def test_app_secret_needs_its_edit_permission():
    settings = _settings()
    with pytest.raises(SettingPermissionError):
        settings.set_app_sync("billing.api_token", "tok", granted=set())
    settings.set_app_sync("billing.api_token", "tok", granted={MANAGE})
    assert settings.get_secret_sync("billing.api_token") == "tok"


def test_app_value_is_the_fallback_for_a_user_secret():
    settings = _settings()
    settings.set_app_sync("email.app_password", "shared", granted=set())
    assert settings.get_secret_sync("email.app_password", ALICE) == "shared"
    settings.set_user_sync(ALICE, "email.app_password", "mine")
    assert settings.get_secret_sync("email.app_password", ALICE) == "mine"


def test_store_holds_ciphertext_not_plaintext():
    store = InMemorySettingsStore()
    settings = _settings(store)
    settings.set_user_sync(ALICE, "email.app_password", "hunter2")
    stored = store.get_many_sync(SettingScope.USER, "alice")["email.app_password"]
    assert isinstance(stored, str) and "hunter2" not in stored
    assert FernetCipher(KEY).decrypt(stored) == "hunter2"


def test_json_file_holds_no_plaintext(tmp_path):
    path = tmp_path / "settings.json"
    settings = _settings(JsonFileSettingsStore(path))
    settings.set_user_sync(ALICE, "email.app_password", "hunter2")
    settings.set_app_sync("billing.api_token", "tok-123", granted={MANAGE})
    text = path.read_text(encoding="utf-8")
    assert "hunter2" not in text and "tok-123" not in text
    # a fresh facade on the same file and key reads it back
    assert (
        _settings(JsonFileSettingsStore(path)).get_secret_sync("email.app_password", ALICE)
        == "hunter2"
    )


# masked reads


def test_reads_give_the_marker_or_none():
    settings = _settings()
    assert settings.get_sync("email.app_password", ALICE) is None
    assert settings.effective_sync(ALICE)["email.app_password"] is None
    settings.set_user_sync(ALICE, "email.app_password", "hunter2")
    settings.set_user_sync(ALICE, "email.address", "alice@example.com")
    assert settings.get_sync("email.app_password", ALICE) is SECRET_SET
    effective = settings.effective_sync(ALICE)
    assert effective == {
        "email.app_password": SECRET_SET,
        "billing.api_token": None,
        "email.address": "alice@example.com",
    }
    assert "hunter2" not in repr(effective)
    assert settings.get_sync("email.app_password", BOB) is None


def test_async_reads_are_masked_too():
    async def run():
        settings = _settings()
        await settings.set_user(ALICE, "email.app_password", "hunter2")
        return (
            await settings.get("email.app_password", ALICE),
            (await settings.effective(ALICE))["email.app_password"],
        )

    assert asyncio.run(run()) == (SECRET_SET, SECRET_SET)


def test_the_marker_renders_as_a_mask():
    assert SECRET_SET
    assert str(SECRET_SET) == "••••••••" and repr(SECRET_SET) == "SECRET_SET"
    assert SECRET_SET == SECRET_SET and SECRET_SET != "••••••••"
    assert type(SECRET_SET)() is SECRET_SET
    assert pickle.loads(pickle.dumps(SECRET_SET)) is SECRET_SET


# writes, resets and errors


def test_an_empty_secret_is_rejected():
    with pytest.raises(ValueError, match="reset it instead"):
        _settings().set_user_sync(ALICE, "email.app_password", "")


def test_a_non_str_secret_is_rejected():
    with pytest.raises(ValueError, match="expected a str"):
        _settings().set_user_sync(ALICE, "email.app_password", 123)


def test_reset_clears_a_secret():
    settings = _settings()
    settings.set_user_sync(ALICE, "email.app_password", "hunter2")
    settings.reset_user_sync(ALICE, "email.app_password")
    assert settings.get_secret_sync("email.app_password", ALICE) is None
    assert settings.get_sync("email.app_password", ALICE) is None
    settings.set_app_sync("billing.api_token", "tok", granted={MANAGE})
    settings.reset_app_sync("billing.api_token", granted={MANAGE})
    assert settings.get_secret_sync("billing.api_token") is None


def test_a_wrong_key_raises_on_get_secret_but_reads_still_show_the_marker():
    store = InMemorySettingsStore()
    _settings(store).set_user_sync(ALICE, "email.app_password", "hunter2")
    rekeyed = _settings(store, FernetCipher(FernetCipher.generate_key()))
    with pytest.raises(SecretDecryptError):
        rekeyed.get_secret_sync("email.app_password", ALICE)
    assert rekeyed.get_sync("email.app_password", ALICE) is SECRET_SET


def test_get_secret_rejects_a_setting_that_isnt_secret():
    with pytest.raises(ValueError, match="isn't secret"):
        _settings().get_secret_sync("email.address", ALICE)


def test_get_secret_anonymous_skips_the_user_layer():
    settings = _settings()
    settings.set_user_sync(ALICE, "email.app_password", "hunter2")
    assert settings.get_secret_sync("email.app_password") is None


# FernetCipher


def test_fernet_round_trip_is_not_deterministic():
    cipher = FernetCipher(KEY)
    a, b = cipher.encrypt("päss"), cipher.encrypt("päss")
    assert a != b and cipher.decrypt(a) == cipher.decrypt(b) == "päss"


def test_fernet_tampered_or_garbage_token_raises():
    cipher = FernetCipher(KEY)
    token = cipher.encrypt("hunter2")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    for bad in (tampered, "not-a-token", "é"):
        with pytest.raises(SecretDecryptError):
            cipher.decrypt(bad)


def test_fernet_malformed_key_fails_fast():
    with pytest.raises(ValueError):
        FernetCipher("too-short")


def test_generate_key_is_a_str_fernet_accepts():
    key = FernetCipher.generate_key()
    assert (
        isinstance(key, str)
        and FernetCipher(key.encode()).decrypt(FernetCipher(key).encrypt("x")) == "x"
    )
