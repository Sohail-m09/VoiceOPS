from datetime import timedelta
from types import SimpleNamespace

import pytest
from pwdlib import PasswordHash

from voiceops.core import security
from voiceops.services import auth as auth_module


@pytest.fixture
def jwt_settings(monkeypatch):
    settings = SimpleNamespace(
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters-long",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
    )

    monkeypatch.setattr(security, "get_settings", lambda: settings)
    return settings


def test_create_and_decode_access_token(jwt_settings):
    token = security.create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
    )

    payload = security.decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"


def test_decode_rejects_invalid_token(jwt_settings):
    payload = security.decode_access_token("invalid.token.value")

    assert payload is None


def test_decode_rejects_expired_token(jwt_settings):
    token = security.create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
        expires_delta=timedelta(seconds=-1),
    )

    assert security.decode_access_token(token) is None


def test_create_token_requires_configured_secret(monkeypatch):
    settings = SimpleNamespace(
        jwt_secret_key="too-short",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
    )

    monkeypatch.setattr(security, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        security.create_access_token("user-id")


@pytest.mark.asyncio
async def test_authenticate_user_success(monkeypatch):
    password_hash = PasswordHash.recommended()
    hashed_password = password_hash.hash("CorrectPassword123!")

    expected_user = SimpleNamespace(
        id="user-id",
        email="operator@voiceops.demo",
        password_hash=hashed_password,
        is_active=True,
    )

    class FakeUserRepository:
        def __init__(self, session):
            pass

        async def get_by_email(self, email):
            return expected_user

    monkeypatch.setattr(
        auth_module,
        "UserRepository",
        FakeUserRepository,
    )

    service = auth_module.AuthService(session=None)

    user = await service.authenticate_user(
        "operator@voiceops.demo",
        "CorrectPassword123!",
    )

    assert user is expected_user


@pytest.mark.asyncio
async def test_authenticate_user_rejects_wrong_password(monkeypatch):
    password_hash = PasswordHash.recommended()

    expected_user = SimpleNamespace(
        id="user-id",
        email="operator@voiceops.demo",
        password_hash=password_hash.hash("CorrectPassword123!"),
        is_active=True,
    )

    class FakeUserRepository:
        def __init__(self, session):
            pass

        async def get_by_email(self, email):
            return expected_user

    monkeypatch.setattr(
        auth_module,
        "UserRepository",
        FakeUserRepository,
    )

    service = auth_module.AuthService(session=None)

    user = await service.authenticate_user(
        "operator@voiceops.demo",
        "WrongPassword123!",
    )

    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_rejects_inactive_user(monkeypatch):
    expected_user = SimpleNamespace(
        id="user-id",
        email="operator@voiceops.demo",
        password_hash="unused",
        is_active=False,
    )

    class FakeUserRepository:
        def __init__(self, session):
            pass

        async def get_by_email(self, email):
            return expected_user

    monkeypatch.setattr(
        auth_module,
        "UserRepository",
        FakeUserRepository,
    )

    service = auth_module.AuthService(session=None)

    user = await service.authenticate_user(
        "operator@voiceops.demo",
        "CorrectPassword123!",
    )

    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_rejects_unknown_email(monkeypatch):
    class FakeUserRepository:
        def __init__(self, session):
            pass

        async def get_by_email(self, email):
            return None

    monkeypatch.setattr(
        auth_module,
        "UserRepository",
        FakeUserRepository,
    )

    service = auth_module.AuthService(session=None)

    user = await service.authenticate_user(
        "unknown@voiceops.demo",
        "CorrectPassword123!",
    )

    assert user is None
