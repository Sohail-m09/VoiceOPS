from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voiceops.database.connection import AsyncSessionLocal
from voiceops.database.models import UserWarehouse
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutor
from voiceops.harness.policy_engine import PolicyEngine, ToolPolicy
from voiceops.harness.tool_registry import ToolDefinition, ToolRegistry
from voiceops.repositories.products import ProductRepository
from voiceops.repositories.warehouses import WarehouseRepository
from voiceops.services.exceptions import NotFoundError
from voiceops.services.orders import OrderService

ORDER_TOOL_NAME = "get_order_details"


class OrderToolArguments(BaseModel):
    """Validated arguments for looking up a warehouse transfer order."""

    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(min_length=1, max_length=50)

    @field_validator("order_number")
    @classmethod
    def validate_order_number(cls, value: str) -> str:
        value = value.strip().upper()

        if not value:
            raise ValueError("Order number cannot be empty.")

        return value


class OrderLookupError(Exception):
    """Raised when order information cannot be retrieved."""


class OrderAccessDeniedError(Exception):
    """Raised when the user cannot access an order's warehouses."""


async def _get_order_details(
    *,
    order_number: str,
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    async with session_factory() as session:
        service = OrderService(session)

        try:
            order = await service.get_order_details(order_number)
        except NotFoundError as exc:
            raise OrderLookupError(str(exc)) from exc

        warehouse_ids = {
            order["source_warehouse_id"],
            order["destination_warehouse_id"],
        }

        # Admins can access orders across all warehouses.
        if context.user_role != "admin":
            statement = select(UserWarehouse.warehouse_id).where(
                UserWarehouse.user_id == context.user_id,
                UserWarehouse.warehouse_id.in_(warehouse_ids),
            )
            result = await session.execute(statement)
            accessible_warehouse_ids = set(result.scalars().all())

            # Both warehouses are required to reveal the complete transfer.
            if not warehouse_ids.issubset(accessible_warehouse_ids):
                raise OrderAccessDeniedError("Access to both order warehouses is required.")

        warehouses = WarehouseRepository(session)
        products = ProductRepository(session)

        source = await warehouses.get_by_id(order["source_warehouse_id"])
        destination = await warehouses.get_by_id(order["destination_warehouse_id"])

        if source is None or destination is None:
            raise OrderLookupError(
                "One or more warehouses associated with this order were not found."
            )

        enriched_items = []

        for item in order["items"]:
            product = await products.get_by_id(item["product_id"])

            if product is None:
                raise OrderLookupError(
                    f"Product {item['product_id']} associated with this order was not found."
                )

            enriched_items.append(
                {
                    "product_id": str(item["product_id"]),
                    "sku": product.sku,
                    "product_name": product.name,
                    "quantity_ordered": item["quantity_ordered"],
                }
            )

        return {
            "order_id": str(order["id"]),
            "order_number": order["order_number"],
            "status": order["status"],
            "created_at": order["created_at"].isoformat(),
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
            "items": enriched_items,
            "item_count": len(enriched_items),
        }


def create_order_executor(
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> ToolExecutor:
    """Create a harness executor containing the read-only order tool."""

    registry = ToolRegistry()

    async def get_order_details_handler(
        order_number: str,
    ) -> dict[str, Any]:
        return await _get_order_details(
            order_number=order_number,
            context=context,
            session_factory=session_factory,
        )

    registry.register(
        ToolDefinition(
            name=ORDER_TOOL_NAME,
            description=(
                "Retrieve an existing warehouse transfer order, its status, "
                "warehouses, creation time, and ordered products."
            ),
            args_schema=OrderToolArguments,
            handler=get_order_details_handler,
            requires_idempotency=False,
        )
    )

    policy_engine = PolicyEngine(
        {
            ORDER_TOOL_NAME: ToolPolicy(
                allowed_roles=frozenset(
                    {
                        "admin",
                        "warehouse_manager",
                        "operator",
                        "analyst",
                    }
                ),
                # Actual warehouse access is checked against PostgreSQL
                # inside the handler, including the admin exception.
                requires_warehouse_access=False,
            )
        }
    )

    return ToolExecutor(
        registry=registry,
        policy_engine=policy_engine,
    )
