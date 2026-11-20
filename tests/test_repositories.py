import asyncio
from unittest.mock import AsyncMock, MagicMock

from voiceops.database.models import User
from voiceops.repositories.base import BaseRepository
from voiceops.repositories.users import UserRepository


def test_user_repository_get_by_email():
    expected_user = object()

    result = MagicMock()
    result.scalar_one_or_none.return_value = expected_user

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    repository = UserRepository(session)

    user = asyncio.run(repository.get_by_email("operator@voiceops.demo"))

    assert user is expected_user
    session.execute.assert_awaited_once()


def test_base_repository_create_flushes_record():
    session = MagicMock()
    session.flush = AsyncMock()

    repository = BaseRepository(session, User)

    user = asyncio.run(
        repository.create(
            {
                "full_name": "Test Operator",
                "email": "test@voiceops.demo",
                "password_hash": "test-hash",
                "role": "operator",
            }
        )
    )

    assert isinstance(user, User)
    assert user.email == "test@voiceops.demo"

    session.add.assert_called_once_with(user)
    session.flush.assert_awaited_once()
    session.commit.assert_not_called()


def test_base_repository_rejects_primary_key_updates():
    session = MagicMock()

    user = User(
        full_name="Test Operator",
        email="test@voiceops.demo",
        password_hash="test-hash",
        role="operator",
    )

    session.get = AsyncMock(return_value=user)
    session.flush = AsyncMock()

    repository = BaseRepository(session, User)

    try:
        asyncio.run(
            repository.update(
                user.id,
                {"id": user.id},
            )
        )
    except ValueError as error:
        assert "primary key" in str(error).lower()
    else:
        raise AssertionError("Primary key update should be rejected.")

    session.flush.assert_not_awaited()
