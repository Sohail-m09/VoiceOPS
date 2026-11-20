from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.core.security import decode_access_token
from voiceops.database.connection import get_db
from voiceops.database.models.user_warehouse import UserWarehouse
from voiceops.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
):
    """Validate the bearer token and return the authenticated user."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    payload = decode_access_token(credentials.credentials)

    if payload is None:
        raise unauthorized

    try:
        user_id = UUID(payload["sub"])
    except (ValueError, TypeError):
        raise unauthorized from None

    repository = UserRepository(session)
    user = await repository.get_by_id(user_id)

    if user is None or not user.is_active:
        raise unauthorized

    # Finish the authentication lookup transaction.
    await session.commit()

    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Allow access only to users with one of the specified roles."""

    async def role_checker(
        current_user=Depends(get_current_user),
    ):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker


async def require_warehouse_access(
    warehouse_id: UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Allow admins or users assigned to the requested warehouse."""

    if current_user.role == "admin":
        return current_user

    assignment = await session.scalar(
        select(UserWarehouse.user_id).where(
            UserWarehouse.user_id == current_user.id,
            UserWarehouse.warehouse_id == warehouse_id,
        )
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this warehouse.",
        )

    return current_user
