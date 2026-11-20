from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from voiceops.config import get_settings


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for an authenticated user."""

    settings = get_settings()

    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")

    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""

    settings = get_settings()

    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if not payload.get("sub"):
            return None

        return payload

    except InvalidTokenError:
        return None
