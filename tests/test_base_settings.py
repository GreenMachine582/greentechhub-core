import pytest
from pydantic import ValidationError

from greentechhub_core.config import GTHBaseSettings


def test_loads_secret_key_and_log_level_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = GTHBaseSettings()
    assert settings.secret_key == "super-secret"
    assert settings.log_level == "DEBUG"


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = GTHBaseSettings()
    assert settings.log_level == "INFO"


def test_missing_secret_key_raises_validation_error(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    with pytest.raises(ValidationError):
        GTHBaseSettings()


def test_env_var_matching_is_case_insensitive(monkeypatch):
    # Lowercase env vars should also resolve to the lowercase fields.
    monkeypatch.setenv("secret_key", "lower-case-secret")
    settings = GTHBaseSettings()
    assert settings.secret_key == "lower-case-secret"


def test_subclass_can_add_extra_fields(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    monkeypatch.setenv("ASYNC_DATABASE_URL", "postgresql+asyncpg://localhost/db")

    class Settings(GTHBaseSettings):
        ASYNC_DATABASE_URL: str

    settings = Settings()
    assert settings.secret_key == "super-secret"
    assert settings.ASYNC_DATABASE_URL == "postgresql+asyncpg://localhost/db"


def test_loads_secret_key_from_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET_KEY=from-dotenv\n")
    settings = GTHBaseSettings()
    assert settings.secret_key == "from-dotenv"


def test_real_env_var_takes_precedence_over_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET_KEY=from-dotenv\n")
    monkeypatch.setenv("SECRET_KEY", "from-real-env")
    settings = GTHBaseSettings()
    assert settings.secret_key == "from-real-env"
