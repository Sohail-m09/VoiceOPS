from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models import Order, OrderItem
from voiceops.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    async def get_by_order_number(
        self,
        order_number: str,
    ) -> Order | None:
        statement = select(Order).where(Order.order_number == order_number)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Order]:
        if limit < 1 or offset < 0:
            raise ValueError("Invalid pagination values.")

        statement = (
            select(Order)
            .where(Order.status == status)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create_items(
        self,
        order_id,
        items: list[dict],
    ) -> list[OrderItem]:
        """Create order items for an existing order."""

        records = [
            OrderItem(
                order_id=order_id,
                product_id=item["product_id"],
                quantity_ordered=item["quantity_ordered"],
            )
            for item in items
        ]

        self.session.add_all(records)

        await self.session.flush()

        return records

    async def list_items(
        self,
        order_id,
    ) -> list[OrderItem]:
        """Retrieve all items belonging to an order."""

        statement = select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)

        result = await self.session.execute(statement)

        return list(result.scalars().all())
