from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voiceops.database.connection import AsyncSessionLocal
from voiceops.database.models.orders import Order
from voiceops.database.models.shipment import Shipment
from voiceops.database.models.user_warehouse import UserWarehouse
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutor
from voiceops.harness.policy_engine import PolicyEngine, ToolPolicy
from voiceops.harness.tool_registry import ToolDefinition, ToolRegistry
from voiceops.services.exceptions import NotFoundError
from voiceops.services.shipments import ShipmentService

SHIPMENT_TOOL_NAME = "get_shipment_details"


class ShipmentToolArguments(BaseModel):
    """Validated arguments for shipment lookup."""

    model_config = ConfigDict(extra="forbid")

    shipment_number: str = Field(min_length=1, max_length=50)

    @field_validator("shipment_number")
    @classmethod
    def validate_shipment_number(cls, value: str) -> str:
        value = value.strip().upper()

        if not value:
            raise ValueError("Shipment number cannot be empty.")

        return value


class ShipmentLookupError(Exception):
    """Raised when shipment information cannot be retrieved."""


class ShipmentAccessDeniedError(Exception):
    """Raised when the user cannot access shipment warehouses."""


async def _get_shipment_details(
    *,
    shipment_number: str,
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    async with session_factory() as session:
        shipment_statement = select(Shipment).where(Shipment.shipment_number == shipment_number)

        shipment_result = await session.execute(shipment_statement)
        shipment = shipment_result.scalar_one_or_none()

        if shipment is None:
            raise ShipmentLookupError(f"Shipment {shipment_number} was not found.")

        order = await session.get(Order, shipment.order_id)

        if order is None:
            raise ShipmentLookupError("The order associated with this shipment was not found.")

        warehouse_ids = {
            order.source_warehouse_id,
            order.destination_warehouse_id,
        }

        # Admins can access shipments across all warehouses.
        if context.user_role != "admin":
            assignment_statement = select(UserWarehouse.warehouse_id).where(
                UserWarehouse.user_id == context.user_id,
                UserWarehouse.warehouse_id.in_(warehouse_ids),
            )

            assignment_result = await session.execute(assignment_statement)

            accessible_warehouse_ids = set(assignment_result.scalars().all())

            if not warehouse_ids.issubset(accessible_warehouse_ids):
                raise ShipmentAccessDeniedError("Access to both shipment warehouses is required.")

        try:
            service = ShipmentService(session)

            return await service.get_shipment_details(shipment_number)

        except NotFoundError as exc:
            raise ShipmentLookupError(str(exc)) from exc


def create_shipment_executor(
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> ToolExecutor:
    """Create a harness executor containing the shipment lookup tool."""

    registry = ToolRegistry()

    async def get_shipment_details_handler(
        shipment_number: str,
    ) -> dict[str, Any]:
        return await _get_shipment_details(
            shipment_number=shipment_number,
            context=context,
            session_factory=session_factory,
        )

    registry.register(
        ToolDefinition(
            name=SHIPMENT_TOOL_NAME,
            description=(
                "Retrieve an existing shipment's status, tracking events, "
                "associated order, warehouses, and shipped and received "
                "product quantities."
            ),
            args_schema=ShipmentToolArguments,
            handler=get_shipment_details_handler,
            requires_idempotency=False,
        )
    )

    policy_engine = PolicyEngine(
        {
            SHIPMENT_TOOL_NAME: ToolPolicy(
                allowed_roles=frozenset(
                    {
                        "admin",
                        "warehouse_manager",
                        "operator",
                        "analyst",
                    }
                ),
                # Database assignment checks happen inside the handler.
                requires_warehouse_access=False,
            )
        }
    )

    return ToolExecutor(
        registry=registry,
        policy_engine=policy_engine,
    )
