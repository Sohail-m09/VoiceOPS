
import pytest
from pydantic import SecretStr, ValidationError

from voiceops.config import Settings


def test_gemini_embedding_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.gemini_embedding_model == "gemini-embedding-2"
    assert settings.gemini_embedding_dimensions == 768
    assert settings.gemini_api_key is None


def test_gemini_embedding_custom_settings() -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-api-key",
        gemini_embedding_model="custom-embedding-model",
        gemini_embedding_dimensions=768,
    )

    assert isinstance(settings.gemini_api_key, SecretStr)
    assert settings.gemini_api_key.get_secret_value() == "test-api-key"
    assert settings.gemini_embedding_model == "custom-embedding-model"
    assert settings.gemini_embedding_dimensions == 768


def test_gemini_api_key_is_masked() -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-api-key",
    )

    assert "test-api-key" not in str(settings.gemini_api_key)


def test_gemini_embedding_dimensions_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            gemini_embedding_dimensions=0,
        )


def test_gemini_embedding_dimensions_cannot_exceed_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            gemini_embedding_dimensions=3073,
        )
