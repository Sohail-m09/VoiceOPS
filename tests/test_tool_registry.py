
import pytest
from pydantic import BaseModel, ConfigDict

from voiceops.harness.tool_registry import (
    ToolAlreadyRegisteredError,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)


class InventoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: str


def get_inventory(warehouse_id: str) -> dict[str, str]:
    return {"warehouse_id": warehouse_id, "status": "available"}


def get_order_details(order_number: str) -> dict[str, str]:
    return {"order_number": order_number, "status": "draft"}


def create_inventory_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_inventory",
        description="Retrieve warehouse inventory.",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )


def test_register_and_retrieve_tool():
    registry = ToolRegistry()
    tool = create_inventory_tool()

    registry.register(tool)

    registered_tool = registry.get("get_inventory")

    assert registered_tool is tool
    assert registered_tool.name == "get_inventory"
    assert registered_tool.handler is get_inventory
    assert registered_tool.args_schema is InventoryArguments


def test_register_multiple_tools():
    registry = ToolRegistry()

    inventory_tool = create_inventory_tool()

    order_tool = ToolDefinition(
        name="get_order_details",
        description="Retrieve order information.",
        args_schema=InventoryArguments,
        handler=get_order_details,
    )

    registry.register(inventory_tool)
    registry.register(order_tool)

    assert len(registry) == 2
    assert len(registry.list_tools()) == 2


def test_duplicate_tool_registration_is_rejected():
    registry = ToolRegistry()
    tool = create_inventory_tool()

    registry.register(tool)

    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register(tool)


def test_missing_tool_raises_error():
    registry = ToolRegistry()

    with pytest.raises(ToolNotFoundError):
        registry.get("unknown_tool")


def test_empty_tool_name_is_rejected():
    registry = ToolRegistry()

    tool = ToolDefinition(
        name="   ",
        description="Retrieve warehouse inventory.",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )

    with pytest.raises(ValueError, match="Tool name cannot be empty"):
        registry.register(tool)


def test_whitespace_in_tool_name_is_rejected():
    registry = ToolRegistry()

    tool = ToolDefinition(
        name=" get_inventory ",
        description="Retrieve warehouse inventory.",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )

    with pytest.raises(
        ValueError,
        match="leading or trailing whitespace",
    ):
        registry.register(tool)


def test_empty_tool_description_is_rejected():
    registry = ToolRegistry()

    tool = ToolDefinition(
        name="get_inventory",
        description="   ",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )

    with pytest.raises(
        ValueError,
        match="Tool description cannot be empty",
    ):
        registry.register(tool)


def test_registry_starts_empty():
    registry = ToolRegistry()

    assert len(registry) == 0
    assert registry.list_tools() == ()


def test_non_pydantic_argument_schema_is_rejected():
    registry = ToolRegistry()

    tool = ToolDefinition(
        name="get_inventory",
        description="Retrieve warehouse inventory.",
        args_schema=dict,
        handler=get_inventory,
    )

    with pytest.raises(
        TypeError,
        match="must be a Pydantic model",
    ):
        registry.register(tool)
