import re
from typing import Any

from voiceops.agents.shipment_tools import (
    SHIPMENT_TOOL_NAME,
    ShipmentAccessDeniedError,
    ShipmentLookupError,
    create_shipment_executor,
)
from voiceops.agents.state import AgentResult, EvidenceItem
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutionError, ToolExecutor
from voiceops.harness.policy_engine import PolicyDeniedError


class ShipmentAgent:
    """Specialist agent for read-only warehouse shipment investigations."""

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.tool_executor = tool_executor

    SHIPMENT_NUMBER_PATTERN = re.compile(
        r"\bshipment\s+(?:number|no\.?)\s*(?:is\s+|[:=#]\s*|\s+)"
        r"([A-Za-z0-9][A-Za-z0-9-]*)",
        re.IGNORECASE,
    )

    SHIPMENT_LABEL_PATTERN = re.compile(
        r"\bshipment\s+"
        r"(?!status\b|details\b|events\b|history\b|tracking\b|number\b|no\b)"
        r"([A-Za-z0-9][A-Za-z0-9-]*)",
        re.IGNORECASE,
    )

    @classmethod
    def extract_shipment_number(
        cls,
        request_text: str,
    ) -> str | None:
        match = cls.SHIPMENT_NUMBER_PATTERN.search(request_text)

        if match is None:
            match = cls.SHIPMENT_LABEL_PATTERN.search(request_text)

        if match is None:
            return None

        return match.group(1).strip().rstrip(".,;:!?").upper()

    @staticmethod
    def _failure(summary: str, error: str) -> dict[str, Any]:
        result: AgentResult = {
            "status": "failed",
            "summary": summary,
            "data": {},
        }

        return {
            "shipment_result": result,
            "completed_agents": ["shipment"],
            "evidence": [],
            "errors": [error],
        }

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        request_text = state.get("request_text", "")
        context_data = state.get("execution_context")

        if not isinstance(request_text, str) or not request_text.strip():
            return self._failure(
                "The shipment request is empty.",
                "Shipment request text is missing.",
            )

        if not isinstance(context_data, dict):
            return self._failure(
                "The shipment request has no trusted execution context.",
                "Execution context is missing.",
            )

        try:
            context = ExecutionContext.model_validate(context_data)
        except Exception:
            return self._failure(
                "The shipment request has an invalid execution context.",
                "Execution context validation failed.",
            )

        shipment_number = self.extract_shipment_number(request_text)

        if shipment_number is None:
            return self._failure(
                "Please provide a shipment number. Example: Check shipment number SHP-123.",
                "Shipment number is missing.",
            )

        try:
            executor = self.tool_executor

            if executor is None:
                executor = create_shipment_executor(context=context)

            shipment = await executor.execute(
                tool_name=SHIPMENT_TOOL_NAME,
                arguments={"shipment_number": shipment_number},
                context=context,
            )

        except PolicyDeniedError:
            return self._failure(
                "Your role is not permitted to perform this shipment lookup.",
                "Shipment tool access was denied.",
            )

        except ToolExecutionError as exc:
            cause = exc.__cause__

            if isinstance(cause, ShipmentAccessDeniedError):
                return self._failure(
                    "You do not have access to both warehouses associated with this shipment.",
                    "Shipment warehouse access denied.",
                )

            if isinstance(cause, ShipmentLookupError):
                return self._failure(
                    str(cause),
                    "Shipment information could not be found.",
                )

            return self._failure(
                "The shipment lookup could not be completed.",
                "Shipment tool execution failed.",
            )

        except Exception:
            return self._failure(
                "The shipment investigation could not be completed.",
                "Shipment investigation failed.",
            )

        latest_event = shipment["events"][-1] if shipment["events"] else None

        latest_event_summary = (
            f" Latest recorded event: {latest_event['event_type']} "
            f"at {latest_event['location'] or 'an unspecified location'}."
            if latest_event
            else " No tracking events are currently recorded."
        )

        result: AgentResult = {
            "status": "success",
            "summary": (
                f"Shipment {shipment['shipment_number']} has status "
                f"{shipment['shipment_status']}. It is associated with "
                f"order {shipment['order']['order_number']}, moving from "
                f"{shipment['source_warehouse']['warehouse_name']} to "
                f"{shipment['destination_warehouse']['warehouse_name']}. "
                f"{shipment['item_count']} product line(s) and "
                f"{shipment['event_count']} tracking event(s) recorded."
                f"{latest_event_summary}"
            ),
            "data": shipment,
        }

        evidence: EvidenceItem = {
            "source": "postgresql.shipments",
            "description": (
                "Shipment details, shipment items, and tracking events "
                "retrieved through ShipmentService.get_shipment_details."
            ),
            "data": shipment,
        }

        return {
            "shipment_result": result,
            "completed_agents": ["shipment"],
            "evidence": [evidence],
            "errors": [],
        }
