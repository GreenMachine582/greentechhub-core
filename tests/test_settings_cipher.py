import base64
import hashlib
import warnings

import pytest

from greentechhub_core.config import GTHBaseSettings
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Setting,
    Settings,
    SettingScope,
    SettingsRegistry,
    SettingType,
)
from greentechhub_core.settings.crypto import (
    FernetCipher,
    derive_cipher_key,
    settings_cipher,
    settings_cipher_key,
)

TOKEN = Setting(key="api.token", type=SettingType.STR, default="", scope=SettingScope.APP,
                label="API token", secret=True)


def _config(monkeypatch, cipher_key=None) -> GTHBaseSettings:
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    if cipher_key is None:
        monkeypatch.delenv("SETTINGS_CIPHER_KEY", raising=False)
    else:
        monkeypatch.setenv("SETTINGS_CIPHER_KEY", cipher_key)
    return GTHBaseSettings(_env_file=None)


def test_a_derived_key_is_stable_per_context_and_usable():
    key = derive_cipher_key("super-secret")
    assert key == derive_cipher_key("super-secret")
    assert key != derive_cipher_key("super-secret", context="other-app")
    assert key != derive_cipher_key("another-secret")
    cipher = FernetCipher(key)
    assert cipher.decrypt(cipher.encrypt("hunter2")) == "hunter2"


def test_a_derived_key_matches_pyfinbots_own_derivation():
    digest = hashlib.sha256(b"pyfinbot-settings:super-secret").digest()
    expected = base64.urlsafe_b64encode(digest).decode("ascii")
    assert derive_cipher_key("super-secret", context="pyfinbot-settings") == expected


def test_an_empty_secret_derives_nothing():
    with pytest.raises(ValueError, match="empty secret"):
        derive_cipher_key("")


def test_a_configured_key_is_used_without_a_warning(monkeypatch):
    configured = FernetCipher.generate_key()
    config = _config(monkeypatch, configured)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert settings_cipher_key(config) == configured


def test_without_one_the_key_is_derived_from_secret_key_with_a_warning(monkeypatch):
    config = _config(monkeypatch)
    with pytest.warns(UserWarning, match="SECRET_KEY"):
        key = settings_cipher_key(config, context="pyfinbot-settings")
    assert key == derive_cipher_key("super-secret", context="pyfinbot-settings")


def test_any_object_with_the_two_attributes_works():
    class Config:
        secret_key = "super-secret"
        settings_cipher_key = ""

    with pytest.warns(UserWarning):
        assert settings_cipher_key(Config()) == derive_cipher_key("super-secret")


def test_settings_cipher_encrypts_secret_settings(monkeypatch):
    config = _config(monkeypatch, FernetCipher.generate_key())
    store = InMemorySettingsStore()
    settings = Settings(SettingsRegistry([TOKEN]), store, env={}, cipher=settings_cipher(config))
    settings.set_app_sync("api.token", "hunter2", granted=set())
    assert store.get_many_sync(SettingScope.APP, None)["api.token"] != "hunter2"
    again = Settings(SettingsRegistry([TOKEN]), store, env={}, cipher=settings_cipher(config))
    assert again.get_secret_sync("api.token") == "hunter2"
