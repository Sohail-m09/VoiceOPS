
import asyncio
from uuid import uuid4

from voiceops.agents.escalation_tools import (
    ESCALATION_TOOL_NAME,
    create_escalation_executor,
)
from voiceops.harness.context_manager import ExecutionContext


def test_escalation_draft_is_prepared_without_execution() -> None:
    async def check_draft() -> None:
        context = ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Prepare an escalation for a delayed shipment",
        )

        executor = create_escalation_executor(context)

        result = await executor.execute(
            tool_name=ESCALATION_TOOL_NAME,
            arguments={
                "issue_summary": (
                    "Shipment has been delayed beyond the expected delivery date."
                ),
                "severity": "high",
                "related_reference": "SHP-1052",
                "supporting_evidence": [
                    "Latest shipment event shows delayed status.",
                    "Expected delivery date has passed.",
                ],
            },
            context=context,
        )

        assert result["status"] == "draft"
        assert result["severity"] == "high"
        assert result["related_reference"] == "SHP-1052"
        assert len(result["supporting_evidence"]) == 2
        assert result["approval_required"] is True
        assert result["execution_status"] == "not_executed"

    asyncio.run(check_draft())
