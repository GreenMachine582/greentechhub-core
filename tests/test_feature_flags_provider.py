import json

import pytest

from greentechhub_core.feature_flags import DEFAULT_ENV_PREFIX, EnvFileFeatureFlagProvider


def test_default_env_prefix_constant_value():
    assert DEFAULT_ENV_PREFIX == "FEATURE_"


# env-only


def test_is_enabled_reads_true_from_env_var(monkeypatch):
    monkeypatch.setenv("FEATURE_NEW_UI", "true")
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("new-ui") is True


def test_is_enabled_reads_false_from_env_var(monkeypatch):
    monkeypatch.setenv("FEATURE_NEW_UI", "false")
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("new-ui") is False


def test_env_var_name_uppercases_the_flag_name(monkeypatch):
    monkeypatch.setenv("FEATURE_REPORTS", "true")
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("reports") is True


def test_env_var_name_replaces_hyphens_with_underscores(monkeypatch):
    monkeypatch.setenv("FEATURE_NEW_DASHBOARD", "true")
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("new-dashboard") is True


@pytest.mark.parametrize("raw", ["true", "1", "yes", "on", "TRUE", "On", " yes "])
def test_is_enabled_accepts_common_truthy_strings(monkeypatch, raw):
    monkeypatch.setenv("FEATURE_X", raw)
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("x") is True


@pytest.mark.parametrize("raw", ["false", "0", "no", "off", "FALSE", "Off", " no "])
def test_is_enabled_accepts_common_falsy_strings(monkeypatch, raw):
    monkeypatch.setenv("FEATURE_X", raw)
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("x") is False


def test_is_enabled_raises_value_error_for_an_unrecognized_env_value(monkeypatch):
    monkeypatch.setenv("FEATURE_X", "enbaled")
    provider = EnvFileFeatureFlagProvider()
    with pytest.raises(ValueError, match="x"):
        provider.is_enabled("x")


def test_is_enabled_returns_default_false_when_unset(monkeypatch):
    monkeypatch.delenv("FEATURE_UNSET_FLAG", raising=False)
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("unset-flag") is False


def test_is_enabled_returns_explicit_default_when_unset(monkeypatch):
    monkeypatch.delenv("FEATURE_UNSET_FLAG", raising=False)
    provider = EnvFileFeatureFlagProvider()
    assert provider.is_enabled("unset-flag", default=True) is True


def test_provider_with_no_path_only_checks_env(monkeypatch):
    monkeypatch.setenv("FEATURE_X", "true")
    provider = EnvFileFeatureFlagProvider(path=None)
    assert provider.is_enabled("x") is True
    assert provider.is_enabled("never-set") is False


def test_custom_env_prefix_is_honored(monkeypatch):
    monkeypatch.setenv("MYAPP_X", "true")
    provider = EnvFileFeatureFlagProvider(env_prefix="MYAPP_")
    assert provider.is_enabled("x") is True


# file-only


def test_is_enabled_reads_true_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FEATURE_NEW_UI", raising=False)
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": True}))
    provider = EnvFileFeatureFlagProvider(path=path)
    assert provider.is_enabled("new-ui") is True


def test_is_enabled_reads_false_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FEATURE_NEW_UI", raising=False)
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": False}))
    provider = EnvFileFeatureFlagProvider(path=path)
    assert provider.is_enabled("new-ui") is False


def test_flag_missing_from_file_returns_default(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"other-flag": True}))
    provider = EnvFileFeatureFlagProvider(path=path)
    assert provider.is_enabled("new-ui", default=True) is True


def test_constructor_raises_file_not_found_for_a_missing_explicit_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        EnvFileFeatureFlagProvider(path=tmp_path / "does-not-exist.json")


def test_constructor_raises_value_error_for_malformed_json(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text("{not valid json")
    with pytest.raises(ValueError, match="not valid JSON"):
        EnvFileFeatureFlagProvider(path=path)


def test_constructor_raises_value_error_for_a_non_object_top_level(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text(json.dumps([True, False]))
    with pytest.raises(ValueError, match="JSON object"):
        EnvFileFeatureFlagProvider(path=path)


def test_constructor_raises_value_error_naming_the_offending_key_for_a_non_bool_value(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": "yes"}))
    with pytest.raises(ValueError, match="new-ui"):
        EnvFileFeatureFlagProvider(path=path)


def test_path_accepts_a_plain_string(tmp_path, monkeypatch):
    monkeypatch.delenv("FEATURE_NEW_UI", raising=False)
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": True}))
    provider = EnvFileFeatureFlagProvider(path=str(path))
    assert provider.is_enabled("new-ui") is True


# precedence


def test_env_var_takes_precedence_over_a_conflicting_file_value_true_wins(tmp_path, monkeypatch):
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": False}))
    monkeypatch.setenv("FEATURE_NEW_UI", "true")
    provider = EnvFileFeatureFlagProvider(path=path)
    assert provider.is_enabled("new-ui") is True


def test_env_var_takes_precedence_over_a_conflicting_file_value_false_wins(tmp_path, monkeypatch):
    path = tmp_path / "flags.json"
    path.write_text(json.dumps({"new-ui": True}))
    monkeypatch.setenv("FEATURE_NEW_UI", "false")
    provider = EnvFileFeatureFlagProvider(path=path)
    assert provider.is_enabled("new-ui") is False

