from datetime import datetime
from uuid import UUID

from voiceops.schemas.common import ORMResponse


class InventoryResponse(ORMResponse):
    warehouse_id: UUID
    product_id: UUID
    quantity_on_hand: int
    quantity_reserved: int
    available_quantity: int
    created_at: datetime
    updated_at: datetime
