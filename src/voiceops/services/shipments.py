from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models.order_item import OrderItem
from voiceops.database.models.orders import Order
from voiceops.database.models.product import Product
from voiceops.database.models.shipment_event import ShipmentEvent
from voiceops.database.models.shipment_item import ShipmentItem
from voiceops.repositories.shipments import ShipmentRepository
from voiceops.repositories.warehouses import WarehouseRepository
from voiceops.services.exceptions import NotFoundError


class ShipmentService:
    """Read-only business operations for warehouse shipments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.shipments = ShipmentRepository(session)
        self.warehouses = WarehouseRepository(session)

    async def get_shipment_details(
        self,
        shipment_number: str,
    ) -> dict[str, Any]:
        """Retrieve shipment, order, warehouse, item, and tracking details."""

        shipment = await self.shipments.get_by_shipment_number(shipment_number)

        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_number} was not found.")

        order = await self.session.get(Order, shipment.order_id)

        if order is None:
            raise NotFoundError(f"Order associated with shipment {shipment_number} was not found.")

        source = await self.warehouses.get_by_id(order.source_warehouse_id)
        destination = await self.warehouses.get_by_id(order.destination_warehouse_id)

        if source is None or destination is None:
            raise NotFoundError(
                "One or more warehouses associated with this shipment were not found."
            )

        items_statement = (
            select(ShipmentItem)
            .where(ShipmentItem.shipment_id == shipment.id)
            .order_by(ShipmentItem.id)
        )

        items_result = await self.session.execute(items_statement)
        shipment_items = list(items_result.scalars().all())

        items = []

        for shipment_item in shipment_items:
            order_item = await self.session.get(
                OrderItem,
                shipment_item.order_item_id,
            )

            if order_item is None:
                raise NotFoundError(
                    f"Order item {shipment_item.order_item_id} "
                    "associated with this shipment was not found."
                )

            product = await self.session.get(
                Product,
                order_item.product_id,
            )

            if product is None:
                raise NotFoundError(
                    f"Product {order_item.product_id} associated with this shipment was not found."
                )

            items.append(
                {
                    "shipment_item_id": shipment_item.id,
                    "order_item_id": order_item.id,
                    "product_id": str(product.id),
                    "sku": product.sku,
                    "product_name": product.name,
                    "quantity_ordered": order_item.quantity_ordered,
                    "quantity_shipped": shipment_item.quantity_shipped,
                    "quantity_received": shipment_item.quantity_received,
                    "quantity_remaining": (
                        shipment_item.quantity_shipped - shipment_item.quantity_received
                    ),
                }
            )

        events_statement = (
            select(ShipmentEvent)
            .where(ShipmentEvent.shipment_id == shipment.id)
            .order_by(
                ShipmentEvent.event_time.asc(),
                ShipmentEvent.id.asc(),
            )
        )

        events_result = await self.session.execute(events_statement)
        shipment_events = list(events_result.scalars().all())

        events = [
            {
                "event_id": event.id,
                "event_type": event.event_type,
                "description": event.description,
                "location": event.location,
                "event_time": event.event_time.isoformat(),
            }
            for event in shipment_events
        ]

        return {
            "shipment_id": str(shipment.id),
            "shipment_number": shipment.shipment_number,
            "shipment_status": shipment.status,
            "created_at": shipment.created_at.isoformat(),
            "updated_at": shipment.updated_at.isoformat(),
            "delivered_at": (shipment.delivered_at.isoformat() if shipment.delivered_at else None),
            "received_at": (shipment.received_at.isoformat() if shipment.received_at else None),
            "order": {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "order_status": order.status,
            },
            "source_warehouse": {
                "warehouse_id": str(source.id),
                "warehouse_code": source.code,
                "warehouse_name": source.name,
            },
            "destination_warehouse": {
                "warehouse_id": str(destination.id),
                "warehouse_code": destination.code,
                "warehouse_name": destination.name,
            },
            "items": items,
            "item_count": len(items),
            "events": events,
            "event_count": len(events),
        }
