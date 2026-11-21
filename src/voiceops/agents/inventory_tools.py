
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voiceops.database.connection import AsyncSessionLocal
from voiceops.database.models.user_warehouse import UserWarehouse
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutor
from voiceops.harness.policy_engine import PolicyEngine, ToolPolicy
from voiceops.harness.tool_registry import ToolDefinition, ToolRegistry
from voiceops.repositories.products import ProductRepository
from voiceops.repositories.warehouses import WarehouseRepository
from voiceops.services.exceptions import NotFoundError
from voiceops.services.inventory import InventoryService

INVENTORY_TOOL_NAME = "get_inventory_stock"


class InventoryToolArguments(BaseModel):
    """Validated arguments for an inventory stock lookup."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=100)
    warehouse_code: str = Field(min_length=1, max_length=100)

    @field_validator("sku", "warehouse_code")
    @classmethod
    def clean_identifier(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Identifier cannot be empty.")

        return value


class InventoryLookupError(Exception):
    """Raised when a product, warehouse, or stock record is missing."""


class InventoryAccessDeniedError(Exception):
    """Raised when the user cannot access the requested warehouse."""


async def _get_inventory_stock(
    *,
    sku: str,
    warehouse_code: str,
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict:
    """Resolve identifiers, authorize access, and retrieve actual stock."""

    async with session_factory() as session:
        # Resolve the warehouse first so access can be checked before
        # revealing whether a product exists.
        warehouse_repository = WarehouseRepository(session)
        warehouse = await warehouse_repository.get_by_code(warehouse_code)

        if warehouse is None:
            raise InventoryLookupError("Warehouse not found.")

        # Admins can access every warehouse.
        # Other users must have a current database assignment.
        if context.user_role != "admin":
            assignment = await session.scalar(
                select(UserWarehouse.user_id).where(
                    UserWarehouse.user_id == context.user_id,
                    UserWarehouse.warehouse_id == warehouse.id,
                )
            )

            if assignment is None:
                raise InventoryAccessDeniedError("You do not have access to this warehouse.")

        product_repository = ProductRepository(session)
        product = await product_repository.get_by_sku(sku)

        if product is None:
            raise InventoryLookupError("Product SKU not found.")

        service = InventoryService(session)

        try:
            stock = await service.get_stock(
                warehouse_id=warehouse.id,
                product_id=product.id,
            )
        except NotFoundError as exc:
            raise InventoryLookupError(
                "No inventory record exists for this product at the requested warehouse."
            ) from exc

        return {
            "sku": product.sku,
            "product_name": product.name,
            "warehouse_code": warehouse.code,
            "warehouse_name": warehouse.name,
            "warehouse_id": str(stock["warehouse_id"]),
            "product_id": str(stock["product_id"]),
            "quantity_on_hand": stock["quantity_on_hand"],
            "quantity_reserved": stock["quantity_reserved"],
            "available_quantity": stock["available_quantity"],
        }


def create_inventory_executor(
    context: ExecutionContext,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> ToolExecutor:
    """Create a registry and executor for inventory tools."""

    registry = ToolRegistry()

    async def inventory_handler(
        *,
        sku: str,
        warehouse_code: str,
    ) -> dict:
        return await _get_inventory_stock(
            sku=sku,
            warehouse_code=warehouse_code,
            context=context,
            session_factory=session_factory,
        )

    registry.register(
        ToolDefinition(
            name=INVENTORY_TOOL_NAME,
            description=(
                "Retrieve actual inventory quantities for a product SKU at an authorized warehouse."
            ),
            args_schema=InventoryToolArguments,
            handler=inventory_handler,
            requires_idempotency=False,
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        INVENTORY_TOOL_NAME,
        ToolPolicy(
            allowed_roles=frozenset(
                {
                    "admin",
                    "warehouse_manager",
                    "operator",
                    "analyst",
                }
            ),
            # Warehouse assignment is checked against PostgreSQL
            # inside the handler, with an admin exception.
            requires_warehouse_access=False,
        ),
    )

    return ToolExecutor(
        registry=registry,
        policy_engine=policy_engine,
    )
