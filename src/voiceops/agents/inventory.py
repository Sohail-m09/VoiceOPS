import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voiceops.agents.inventory_tools import (
    INVENTORY_TOOL_NAME,
    InventoryAccessDeniedError,
    InventoryLookupError,
    create_inventory_executor,
)
from voiceops.agents.state import AgentResult, EvidenceItem
from voiceops.database.connection import AsyncSessionLocal
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutionError, ToolExecutor
from voiceops.harness.policy_engine import PolicyDeniedError


class InventoryAgent:
    """Specialist agent for warehouse inventory queries."""

    SKU_PATTERN = re.compile(
        r"\b(?:product\s+)?sku"
        r"(?:\s+is\s+|\s+|[:=#]\s*)"
        r"([A-Za-z0-9][A-Za-z0-9._/-]*)",
        re.IGNORECASE,
    )

    WAREHOUSE_PATTERN = re.compile(
        r"\bwarehouse(?:\s+code)?"
        r"(?:\s+is\s+|\s+|[:=#]\s*)"
        r"([A-Za-z0-9][A-Za-z0-9._/-]*)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.tool_executor = tool_executor

    @classmethod
    def extract_identifiers(
        cls,
        request_text: str,
    ) -> tuple[str | None, str | None]:
        sku_match = cls.SKU_PATTERN.search(request_text)
        warehouse_match = cls.WAREHOUSE_PATTERN.search(request_text)

        sku = sku_match.group(1).strip().rstrip(".,;:!?") if sku_match else None

        warehouse_code = (
            warehouse_match.group(1).strip().rstrip(".,;:!?")
            if warehouse_match
            else None
        )

        return sku, warehouse_code

    @staticmethod
    def _failure(
        summary: str,
        error: str,
    ) -> dict[str, Any]:
        result: AgentResult = {
            "status": "failed",
            "summary": summary,
            "data": {},
        }

        return {
            "inventory_result": result,
            "completed_agents": ["inventory"],
            "evidence": [],
            "errors": [error],
        }

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the inventory investigation."""

        request_text = state.get("request_text", "")
        context_data = state.get("execution_context")

        if not isinstance(request_text, str) or not request_text.strip():
            return self._failure(
                "The inventory request is empty.",
                "Inventory request text is missing.",
            )

        if not isinstance(context_data, dict):
            return self._failure(
                "The inventory request has no trusted execution context.",
                "Execution context is missing.",
            )

        try:
            context = ExecutionContext.model_validate(context_data)
        except Exception:
            return self._failure(
                "The inventory request has an invalid execution context.",
                "Execution context validation failed.",
            )

        sku, warehouse_code = self.extract_identifiers(request_text)

        if not sku or not warehouse_code:
            return self._failure(
                "Please specify both the product SKU and warehouse code. "
                "Example: Check stock for SKU P-101 at warehouse PUN-01.",
                "Product SKU or warehouse code is missing.",
            )

        try:
            executor = self.tool_executor

            if executor is None:
                executor = create_inventory_executor(
                    context=context,
                    session_factory=self.session_factory,
                )

            stock = await executor.execute(
                tool_name=INVENTORY_TOOL_NAME,
                arguments={
                    "sku": sku,
                    "warehouse_code": warehouse_code,
                },
                context=context,
            )

        except PolicyDeniedError:
            return self._failure(
                "Your role is not permitted to perform this inventory lookup.",
                "Inventory tool access was denied.",
            )

        except ToolExecutionError as exc:
            cause = exc.__cause__

            if isinstance(cause, InventoryAccessDeniedError):
                return self._failure(
                    "You do not have access to the requested warehouse.",
                    "Warehouse access denied.",
                )

            if isinstance(cause, InventoryLookupError):
                return self._failure(
                    str(cause),
                    "Inventory information could not be found.",
                )

            return self._failure(
                "The inventory lookup could not be completed.",
                "Inventory tool execution failed.",
            )

        except Exception:
            return self._failure(
                "The inventory lookup could not be completed.",
                "Inventory investigation failed.",
            )

        result: AgentResult = {
            "status": "success",
            "summary": (
                f"{stock['product_name']} ({stock['sku']}) at "
                f"{stock['warehouse_name']} "
                f"({stock['warehouse_code']}): "
                f"{stock['available_quantity']} units available."
            ),
            "data": stock,
        }

        evidence: EvidenceItem = {
            "source": "postgresql.inventory",
            "description": ("Inventory quantities retrieved through InventoryService.get_stock."),
            "data": stock,
        }

        return {
            "inventory_result": result,
            "completed_agents": ["inventory"],
            "evidence": [evidence],
            "errors": [],
        }
