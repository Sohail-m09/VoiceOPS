from datetime import datetime
from uuid import UUID

from voiceops.schemas.common import ORMResponse


class ProductResponse(ORMResponse):
    id: UUID
    sku: str
    name: str
    description: str | None
    unit_of_measure: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
