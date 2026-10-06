"""The adapter settings on GTHBaseSettings (AUTH_ADAPTER, CORS_ALLOWED_ORIGINS,
TRUSTED_PROXIES, ROLE_GROUPS, ROLE_BOOTSTRAP)."""

import pytest
from pydantic_settings import SettingsConfigDict

from greentechhub_core.config import GTHBaseSettings

ADAPTER_VARS = ["AUTH_ADAPTER", "CORS_ALLOWED_ORIGINS", "TRUSTED_PROXIES", "ROLE_GROUPS",
                "ROLE_BOOTSTRAP"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    for name in ADAPTER_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_the_safe_ones():
    settings = GTHBaseSettings(_env_file=None)
    assert settings.auth_adapter == "local"
    assert settings.cors_allowed_origins == ""
    assert settings.trusted_proxies == ""
    assert settings.role_groups == ""
    assert settings.role_bootstrap == ""


def test_read_from_screaming_case_env_vars(monkeypatch):
    monkeypatch.setenv("AUTH_ADAPTER", "forward_auth")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example,https://b.example")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5")
    monkeypatch.setenv("ROLE_GROUPS", "finance=admin|editor")
    monkeypatch.setenv("ROLE_BOOTSTRAP", "alice=admin")
    settings = GTHBaseSettings(_env_file=None)
    assert settings.auth_adapter == "forward_auth"
    assert settings.cors_allowed_origins == "https://a.example,https://b.example"
    assert settings.trusted_proxies == "10.0.0.5"
    assert settings.role_groups == "finance=admin|editor"
    assert settings.role_bootstrap == "alice=admin"


def test_a_service_settings_that_ignores_extras_still_gets_them(monkeypatch):
    # The gap these fields close: an undeclared env var on extra="ignore"
    # Settings used to be dropped.
    class Settings(GTHBaseSettings):
        model_config = SettingsConfigDict(**{**GTHBaseSettings.model_config, "extra": "ignore"})

    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5")
    assert Settings(_env_file=None).trusted_proxies == "10.0.0.5"


def test_a_service_that_already_declares_the_screaming_case_field_keeps_it(monkeypatch):
    class Settings(GTHBaseSettings):
        TRUSTED_PROXIES: str = ""

    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5")
    settings = Settings(_env_file=None)
    assert settings.TRUSTED_PROXIES == "10.0.0.5"
    assert settings.trusted_proxies == "10.0.0.5"
