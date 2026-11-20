from typing import Literal

from pydantic import EmailStr, Field

from voiceops.schemas.common import RequestModel
from voiceops.schemas.users import UserResponse


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(RequestModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
