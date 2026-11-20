from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.repositories.users import UserRepository


class AuthService:
    """Authenticate users using their stored password hashes."""

    def __init__(self, session: AsyncSession) -> None:
        self.user_repository = UserRepository(session)
        self.password_hash = PasswordHash.recommended()

    async def authenticate_user(
        self,
        email: str,
        password: str,
    ):
        """Return the user if credentials are valid and the account is active."""

        user = await self.user_repository.get_by_email(email)

        if user is None:
            return None

        if not user.is_active:
            return None

        try:
            password_valid = self.password_hash.verify(
                password,
                user.password_hash,
            )
        except (ValueError, TypeError):
            return None

        if not password_valid:
            return None

        return user
