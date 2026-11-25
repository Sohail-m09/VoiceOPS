import re
from typing import Any

from voiceops.agents.order_tools import (
    ORDER_TOOL_NAME,
    OrderAccessDeniedError,
    OrderLookupError,
    create_order_executor,
)
from voiceops.agents.state import AgentResult, EvidenceItem, get_effective_request
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutionError, ToolExecutor
from voiceops.harness.policy_engine import PolicyDeniedError


class OrderAgent:
    """Specialist agent for read-only warehouse order investigations."""

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.tool_executor = tool_executor

    ORDER_PATTERN = re.compile(
        r"\b(ORD-[A-Za-z0-9-]+)\b",
        re.IGNORECASE,
    )

    @classmethod
    def extract_order_number(cls, request_text: str) -> str | None:
        match = cls.ORDER_PATTERN.search(request_text)

        if match is None:
            return None

        return match.group(1).upper()

    @staticmethod
    def _failure(summary: str, error: str) -> dict[str, Any]:
        result: AgentResult = {
            "status": "failed",
            "summary": summary,
            "data": {},
        }

        return {
            "order_result": result,
            "completed_agents": ["order"],
            "evidence": [],
            "errors": [error],
        }

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        request_text = get_effective_request(state)
        context_data = state.get("execution_context")

        if not isinstance(request_text, str) or not request_text.strip():
            return self._failure(
                "The order request is empty.",
                "Order request text is missing.",
            )

        if not isinstance(context_data, dict):
            return self._failure(
                "The order request has no trusted execution context.",
                "Execution context is missing.",
            )

        try:
            context = ExecutionContext.model_validate(context_data)
        except Exception:
            return self._failure(
                "The order request has an invalid execution context.",
                "Execution context validation failed.",
            )

        order_number = self.extract_order_number(request_text)

        if order_number is None:
            return self._failure(
                "Please provide an order number. Example: Check order ORD-ABC123.",
                "Order number is missing.",
            )

        try:
            executor = self.tool_executor

            if executor is None:
                executor = create_order_executor(context=context)

            order = await executor.execute(
                tool_name=ORDER_TOOL_NAME,
                arguments={"order_number": order_number},
                context=context,
            )

        except PolicyDeniedError:
            return self._failure(
                "Your role is not permitted to perform this order lookup.",
                "Order tool access was denied.",
            )

        except ToolExecutionError as exc:
            cause = exc.__cause__

            if isinstance(cause, OrderAccessDeniedError):
                return self._failure(
                    "You do not have access to both warehouses associated with this order.",
                    "Order warehouse access denied.",
                )

            if isinstance(cause, OrderLookupError):
                return self._failure(
                    str(cause),
                    "Order information could not be found.",
                )

            return self._failure(
                "The order lookup could not be completed.",
                "Order tool execution failed.",
            )

        except Exception:
            return self._failure(
                "The order investigation could not be completed.",
                "Order investigation failed.",
            )

        item_summary = ", ".join(
            f"{item['sku']} x {item['quantity_ordered']}" for item in order["items"]
        )

        result: AgentResult = {
            "status": "success",
            "summary": (
                f"Order {order['order_number']} has status "
                f"{order['status']}. Transfer from "
                f"{order['source_warehouse']['warehouse_name']} to "
                f"{order['destination_warehouse']['warehouse_name']}. "
                f"Items: {item_summary or 'No items recorded'}."
            ),
            "data": order,
        }

        evidence: EvidenceItem = {
            "source": "postgresql.orders",
            "description": (
                "Order details and ordered items retrieved through OrderService.get_order_details."
            ),
            "data": order,
        }

        return {
            "order_result": result,
            "completed_agents": ["order"],
            "evidence": [evidence],
            "errors": [],
        }
