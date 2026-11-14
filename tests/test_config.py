from voiceops.config import Settings


def test_defaults_are_used_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"


def test_environment_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert Settings(_env_file=None).log_level == "DEBUG"


def test_values_are_read_from_env_file_and_unknown_keys_are_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=production\nSOME_UNUSED_KEY=1\n")
    assert Settings(_env_file=env_file).app_env == "production"
