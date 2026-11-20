from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models import Shipment
from voiceops.repositories.base import BaseRepository


class ShipmentRepository(BaseRepository[Shipment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Shipment)

    async def get_by_shipment_number(
        self,
        shipment_number: str,
    ) -> Shipment | None:
        statement = select(Shipment).where(Shipment.shipment_number == shipment_number)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
