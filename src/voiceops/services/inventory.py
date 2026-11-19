from uuid import UUID

from voiceops.repositories.inventory import InventoryRepository
from voiceops.services.exceptions import NotFoundError


class InventoryService:
    """Business operations related to warehouse inventory."""

    def __init__(self, session) -> None:
        self.repository = InventoryRepository(session)

    async def get_stock(
        self,
        warehouse_id: UUID,
        product_id: UUID,
    ):
        inventory = await self.repository.get_by_warehouse_and_product(
            warehouse_id,
            product_id,
        )

        if inventory is None:
            raise NotFoundError("Inventory record not found for this warehouse and product.")

        return {
            "warehouse_id": inventory.warehouse_id,
            "product_id": inventory.product_id,
            "quantity_on_hand": inventory.quantity_on_hand,
            "quantity_reserved": inventory.quantity_reserved,
            "available_quantity": (inventory.quantity_on_hand - inventory.quantity_reserved),
        }

    async def list_warehouse_inventory(
        self,
        warehouse_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ):
        return await self.repository.list_by_warehouse(
            warehouse_id,
            limit,
            offset,
        )
