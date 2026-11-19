
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models import Order
from voiceops.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    async def get_by_order_number(
        self,
        order_number: str,
    ) -> Order | None:
        statement = select(Order).where(
            Order.order_number == order_number
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Order]:
        statement = (
            select(Order)
            .where(Order.status == status)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())
