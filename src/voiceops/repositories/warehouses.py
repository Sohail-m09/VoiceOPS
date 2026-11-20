from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models import Warehouse
from voiceops.repositories.base import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Warehouse)

    async def get_by_code(self, code: str) -> Warehouse | None:
        statement = select(Warehouse).where(Warehouse.code == code)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
