
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models import Inventory
from voiceops.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[Inventory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Inventory)

    async def get_by_warehouse_and_product(
        self,
        warehouse_id: UUID,
        product_id: UUID,
    ) -> Inventory | None:
        return await self.get_by_id(
            (warehouse_id, product_id)
        )

    async def list_by_warehouse(
        self,
        warehouse_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Inventory]:
        statement = (
            select(Inventory)
            .where(Inventory.warehouse_id == warehouse_id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())
