"""Service basics on GTHBaseSettings: environment, lock_dir and
lock_directory(), and the opt-in ephemeral secret key and development CORS
default. Without the opt-ins nothing changes for existing services."""

import tempfile
import warnings
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from greentechhub_core.config import GTHBaseSettings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("SECRET_KEY", "ENVIRONMENT", "LOCK_DIR", "CORS_ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


class _Opted(GTHBaseSettings):
    ephemeral_secret_key: ClassVar[bool] = True
    cors_allow_all_in_development: ClassVar[bool] = True


def test_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    settings = GTHBaseSettings(_env_file=None)
    assert settings.environment == "development"
    assert settings.lock_dir == ""
    assert settings.cors_allowed_origins == ""  # no dev default without the opt-in


def test_environment_and_lock_dir_from_the_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOCK_DIR", str(tmp_path))
    settings = GTHBaseSettings(_env_file=None)
    assert settings.environment == "production"
    assert settings.lock_directory() == str(tmp_path)


def test_lock_directory_defaults_under_the_temp_dir(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    expected = str(Path(tempfile.gettempdir()) / "gth-locks")
    assert GTHBaseSettings(_env_file=None).lock_directory() == expected


def test_secret_key_is_still_required_without_the_opt_in():
    with pytest.raises(ValidationError):
        GTHBaseSettings(_env_file=None)


def test_the_ephemeral_secret_key_opt_in_fills_one_and_warns():
    with pytest.warns(UserWarning, match="SECRET_KEY is not set"):
        first = _Opted(_env_file=None)
    with pytest.warns(UserWarning):
        second = _Opted(_env_file=None)
    assert len(first.secret_key) == 64 and first.secret_key != second.secret_key


def test_a_set_secret_key_is_kept_without_a_warning(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-env")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _Opted(_env_file=None).secret_key == "from-env"


def test_development_cors_default_with_the_opt_in(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    assert _Opted(_env_file=None).cors_allowed_origins == "*"
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example")
    assert _Opted(_env_file=None).cors_allowed_origins == "https://a.example"


def test_production_without_cors_origins_warns_with_the_opt_in(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.warns(UserWarning, match="CORS_ALLOWED_ORIGINS is not set"):
        settings = _Opted(_env_file=None)
    assert settings.cors_allowed_origins == ""


def test_no_cors_warning_without_the_opt_in(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        GTHBaseSettings(_env_file=None)


_MOVED = "each user sets their own email account at /settings"


class _Retiring(GTHBaseSettings):
    retired: ClassVar[dict[str, str]] = {
        "GMAIL_ADDRESS": _MOVED,
        "GMAIL_MAILBOX": _MOVED,
        "ACCESS_TOKEN_EXPIRE_MINUTES": "API tokens last 24 hours",
    }


@pytest.fixture
def _no_retired_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    for name in _Retiring.retired:
        monkeypatch.delenv(name, raising=False)


def _retired_warnings(record) -> list[str]:
    return [str(w.message) for w in record if "no longer used" in str(w.message)]


@pytest.mark.usefixtures("_no_retired_env")
def test_a_retired_env_var_warns_naming_its_replacement(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "me@example.com")
    with pytest.warns(UserWarning) as record:
        _Retiring(_env_file=None)
    assert _retired_warnings(record) == [
        f"GMAIL_ADDRESS is no longer used: {_MOVED}. Remove them from the environment/.env."
    ]


@pytest.mark.usefixtures("_no_retired_env")
def test_retired_env_vars_warn_once_per_replacement(monkeypatch):
    for name in _Retiring.retired:
        monkeypatch.setenv(name, "x")
    with pytest.warns(UserWarning) as record:
        _Retiring(_env_file=None)
    assert _retired_warnings(record) == [
        f"GMAIL_ADDRESS, GMAIL_MAILBOX are no longer used: {_MOVED}. "
        "Remove them from the environment/.env.",
        "ACCESS_TOKEN_EXPIRE_MINUTES is no longer used: API tokens last 24 hours. "
        "Remove them from the environment/.env.",
    ]


@pytest.mark.usefixtures("_no_retired_env")
def test_an_unset_or_empty_retired_env_var_is_quiet(monkeypatch):
    monkeypatch.setenv("GMAIL_MAILBOX", "")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _Retiring(_env_file=None)


@pytest.mark.usefixtures("_no_retired_env")
def test_a_lowercase_env_var_name_matches(monkeypatch):
    monkeypatch.setenv("gmail_address", "me@example.com")
    with pytest.warns(UserWarning, match="GMAIL_ADDRESS is no longer used"):
        _Retiring(_env_file=None)


@pytest.mark.usefixtures("_no_retired_env")
def test_a_retired_name_in_dotenv_warns_instead_of_failing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GMAIL_ADDRESS=me@example.com\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="GMAIL_ADDRESS is no longer used"):
        settings = _Retiring(_env_file=env_file)
    assert settings.secret_key == "s"
    with pytest.raises(ValidationError):  # without `retired` it's an unknown extra
        GTHBaseSettings(_env_file=env_file)


def test_no_retired_settings_means_no_warning(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("GMAIL_ADDRESS", "me@example.com")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        GTHBaseSettings(_env_file=None)
