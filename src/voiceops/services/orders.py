from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.repositories.inventory import InventoryRepository
from voiceops.repositories.orders import OrderRepository
from voiceops.repositories.products import ProductRepository
from voiceops.repositories.warehouses import WarehouseRepository
from voiceops.services.audit import AuditService
from voiceops.services.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
    NotFoundError,
)


class OrderService:
    """Business operations for warehouse transfer orders."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self.orders = OrderRepository(session)
        self.warehouses = WarehouseRepository(session)
        self.products = ProductRepository(session)
        self.inventory = InventoryRepository(session)
        self.audit = AuditService(session)

    async def create_transfer_order(
        self,
        source_warehouse_id: UUID,
        destination_warehouse_id: UUID,
        items: list[dict],
        actor_user_id: UUID | None = None,
    ):
        """Create a validated draft transfer order and audit the action."""

        if source_warehouse_id == destination_warehouse_id:
            raise BusinessRuleError("Source and destination warehouses must be different.")

        if not items:
            raise BusinessRuleError("A transfer order must contain at least one item.")

        product_ids = [item["product_id"] for item in items]

        if len(product_ids) != len(set(product_ids)):
            raise BusinessRuleError("Duplicate products are not allowed in one order.")

        for item in items:
            quantity = item["quantity_ordered"]

            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise BusinessRuleError("Order quantities must be integers.")

            if quantity <= 0:
                raise BusinessRuleError("Order quantities must be greater than zero.")

        async with self.session.begin():
            source = await self.warehouses.get_by_id(source_warehouse_id)

            if source is None or not source.is_active:
                raise NotFoundError("Source warehouse does not exist or is inactive.")

            destination = await self.warehouses.get_by_id(destination_warehouse_id)

            if destination is None or not destination.is_active:
                raise NotFoundError("Destination warehouse does not exist or is inactive.")

            for item in items:
                product = await self.products.get_by_id(item["product_id"])

                if product is None or not product.is_active:
                    raise NotFoundError(
                        f"Product {item['product_id']} does not exist or is inactive."
                    )

                stock = await self.inventory.get_by_warehouse_and_product(
                    source_warehouse_id,
                    item["product_id"],
                )

                if stock is None:
                    raise NotFoundError(
                        f"No inventory record exists for product "
                        f"{product.sku} at the source warehouse."
                    )

                available = stock.quantity_on_hand - stock.quantity_reserved

                if item["quantity_ordered"] > available:
                    raise InsufficientStockError(
                        f"Insufficient available stock for "
                        f"{product.sku}. Available: {available}, "
                        f"requested: {item['quantity_ordered']}."
                    )

            order = await self.orders.create(
                {
                    "order_number": f"ORD-{uuid4().hex[:12].upper()}",
                    "source_warehouse_id": source_warehouse_id,
                    "destination_warehouse_id": destination_warehouse_id,
                    "status": "draft",
                }
            )

            await self.orders.create_items(order.id, items)

            await self.audit.record_action(
                actor_user_id=actor_user_id,
                action="transfer_order_created",
                entity_type="order",
                entity_id=str(order.id),
                details={
                    "order_number": order.order_number,
                    "source_warehouse_id": str(source_warehouse_id),
                    "destination_warehouse_id": str(destination_warehouse_id),
                    "item_count": len(items),
                },
            )

            return order

    async def get_order_details(
        self,
        order_number: str,
    ) -> dict:
        """Retrieve an order and its individual items."""

        order = await self.orders.get_by_order_number(order_number)

        if order is None:
            raise NotFoundError(f"Order {order_number} was not found.")

        items = await self.orders.list_items(order.id)

        return {
            "id": order.id,
            "order_number": order.order_number,
            "source_warehouse_id": order.source_warehouse_id,
            "destination_warehouse_id": order.destination_warehouse_id,
            "status": order.status,
            "created_at": order.created_at,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "quantity_ordered": item.quantity_ordered,
                }
                for item in items
            ],
        }
