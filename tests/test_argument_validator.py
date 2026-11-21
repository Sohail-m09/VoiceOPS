
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict, Field

from voiceops.harness.argument_validator import (
    ToolArgumentValidationError,
    ToolArgumentValidator,
)
from voiceops.harness.tool_registry import ToolDefinition


class InventoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID


class OrderArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(min_length=3, max_length=30)


def get_inventory(warehouse_id: UUID) -> dict[str, str]:
    return {"warehouse_id": str(warehouse_id)}


def get_order_details(order_number: str) -> dict[str, str]:
    return {"order_number": order_number}


def create_inventory_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_inventory",
        description="Retrieve warehouse inventory.",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )


def create_order_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_order_details",
        description="Retrieve order information.",
        args_schema=OrderArguments,
        handler=get_order_details,
    )


def test_valid_arguments_are_accepted():
    tool = create_inventory_tool()
    warehouse_id = uuid4()

    result = ToolArgumentValidator.validate(
        tool,
        {"warehouse_id": str(warehouse_id)},
    )

    assert result == {"warehouse_id": warehouse_id}
    assert isinstance(result["warehouse_id"], UUID)


def test_invalid_uuid_is_rejected():
    tool = create_inventory_tool()

    with pytest.raises(ToolArgumentValidationError):
        ToolArgumentValidator.validate(
            tool,
            {"warehouse_id": "not-a-valid-uuid"},
        )


def test_missing_required_argument_is_rejected():
    tool = create_inventory_tool()

    with pytest.raises(ToolArgumentValidationError):
        ToolArgumentValidator.validate(tool, {})


def test_unexpected_argument_is_rejected():
    tool = create_inventory_tool()

    with pytest.raises(ToolArgumentValidationError):
        ToolArgumentValidator.validate(
            tool,
            {
                "warehouse_id": str(uuid4()),
                "unexpected": "value",
            },
        )


def test_string_length_constraints_are_enforced():
    tool = create_order_tool()

    with pytest.raises(ToolArgumentValidationError):
        ToolArgumentValidator.validate(
            tool,
            {"order_number": "A"},
        )


def test_valid_order_arguments_are_accepted():
    tool = create_order_tool()

    result = ToolArgumentValidator.validate(
        tool,
        {"order_number": "ORD-1052"},
    )

    assert result == {"order_number": "ORD-1052"}


def test_validator_does_not_execute_tool():
    tool = create_inventory_tool()
    warehouse_id = uuid4()

    result = ToolArgumentValidator.validate(
        tool,
        {"warehouse_id": str(warehouse_id)},
    )

    assert result["warehouse_id"] == warehouse_id
    # Validation only returns arguments; execution belongs to Step 4.
