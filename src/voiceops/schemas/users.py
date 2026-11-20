from datetime import datetime
from uuid import UUID

from voiceops.schemas.common import ORMResponse


class UserResponse(ORMResponse):
    id: UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
