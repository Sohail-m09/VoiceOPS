from datetime import datetime
from uuid import UUID

from voiceops.schemas.common import ORMResponse


class WarehouseResponse(ORMResponse):
    id: UUID
    name: str
    code: str
    address: str | None
    city: str
    state: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
