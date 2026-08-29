"""Tests for src.config: defaults, overrides, validation, caching, and the
no-directory-side-effect guarantee."""

import pytest

from src.config import ConfigError, get_settings

_ENV_VARS = (
    "APP_ENV", "LOG_LEVEL", "DEVICE", "EMBEDDING_MODEL",
    "GENERATION_PROVIDER", "GENERATION_MODEL", "STORAGE_ROOT", "SEC_USER_AGENT",
)


def test_defaults_load_without_any_env_override(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Isolate from whatever a real local .env file happens to contain (e.g.
    # a developer's own GENERATION_PROVIDER/GENERATION_MODEL/OPENROUTER_API_KEY
    # for Task 1.7's live smoke) - clearing os.environ above is not enough,
    # since load_settings() would otherwise repopulate these vars from .env.
    monkeypatch.setattr("src.config.load_dotenv", lambda *a, **k: None)
    get_settings.cache_clear()

    s = get_settings()
    assert s.app_env == "development"
    assert s.log_level == "INFO"
    assert s.device == "auto"
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.generation_provider is None
    assert s.generation_model is None
    assert s.sec_user_agent is None


def test_storage_root_default_is_repo_relative(monkeypatch):
    monkeypatch.delenv("STORAGE_ROOT", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    # relationship, not a personal absolute path literal
    assert s.storage_root == s.repo_root / "data"


def test_repo_root_is_derived_not_hardcoded():
    s = get_settings()
    assert (s.repo_root / "src" / "config.py").is_file()


def test_env_overrides_are_respected(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "alt_data"))
    get_settings.cache_clear()

    s = get_settings()
    assert s.app_env == "test"
    assert s.log_level == "DEBUG"
    assert s.device == "cpu"
    assert s.embedding_model == "test-model"
    assert s.storage_root == (tmp_path / "alt_data").resolve()


@pytest.mark.parametrize(
    "var,bad_value",
    [("APP_ENV", "banana"), ("LOG_LEVEL", "LOUD"), ("DEVICE", "tpu")],
)
def test_invalid_values_raise_config_error(monkeypatch, var, bad_value):
    monkeypatch.setenv(var, bad_value)
    get_settings.cache_clear()
    with pytest.raises(ConfigError):
        get_settings()


def test_get_settings_is_cached_until_cleared(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    get_settings.cache_clear()
    s1 = get_settings()
    assert s1.log_level == "INFO"

    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s2 = get_settings()
    assert s2.log_level == "INFO", "cached value should not change until cache_clear()"

    get_settings.cache_clear()
    s3 = get_settings()
    assert s3.log_level == "DEBUG"


def test_no_directory_created_for_nonexistent_storage_root(monkeypatch, tmp_path):
    target = tmp_path / "does_not_exist_yet"
    monkeypatch.setenv("STORAGE_ROOT", str(target))
    get_settings.cache_clear()

    s = get_settings()
    assert s.storage_root == target.resolve()
    assert not target.exists()
