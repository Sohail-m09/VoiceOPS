from datetime import datetime
from uuid import UUID

from voiceops.schemas.common import ORMResponse


class ShipmentResponse(ORMResponse):
    id: UUID
    shipment_number: str
    order_id: UUID
    status: str
    delivered_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    updated_at: datetime
