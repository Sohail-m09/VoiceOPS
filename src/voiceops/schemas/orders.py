from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from voiceops.schemas.common import ORMResponse, RequestModel


class TransferOrderItemCreate(RequestModel):
    product_id: UUID
    quantity_ordered: int = Field(gt=0, strict=True)


class TransferOrderCreate(RequestModel):
    source_warehouse_id: UUID
    destination_warehouse_id: UUID
    items: list[TransferOrderItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transfer_order(self):
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("Source and destination warehouses must be different.")

        product_ids = [item.product_id for item in self.items]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate products are not allowed in a transfer order.")

        return self


class OrderItemResponse(ORMResponse):
    id: int
    product_id: UUID
    quantity_ordered: int


class OrderResponse(ORMResponse):
    id: UUID
    order_number: str
    source_warehouse_id: UUID
    destination_warehouse_id: UUID
    status: str
    created_at: datetime
    items: list[OrderItemResponse]
