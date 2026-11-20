from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from voiceops.schemas.common import ORMResponse


class AuditLogResponse(ORMResponse):
    id: int
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
