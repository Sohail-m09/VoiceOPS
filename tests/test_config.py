from voiceops.config import Settings


def test_defaults_are_used_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url is None


def test_environment_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert Settings(_env_file=None).log_level == "DEBUG"


def test_database_url_is_read_from_environment(monkeypatch):
    database_url = "postgresql+psycopg://test_user:test_password@127.0.0.1:5432/test_db"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


def test_values_are_read_from_env_file_and_unknown_keys_are_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=production\nSOME_UNUSED_KEY=1\n")

    assert Settings(_env_file=env_file).app_env == "production"
