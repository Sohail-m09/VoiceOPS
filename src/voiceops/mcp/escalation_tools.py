
from typing import Any, Literal

from fastmcp import FastMCP

from voiceops.agents.escalation_tools import (
    ESCALATION_TOOL_NAME,
    create_escalation_executor,
)
from voiceops.harness.context_manager import ExecutionContext


def register_escalation_tools(
    server: FastMCP,
    context: ExecutionContext,
) -> None:
    """Register escalation draft preparation with the MCP server."""

    executor = create_escalation_executor(context)

    @server.tool
    async def prepare_escalation_draft(
        issue_summary: str,
        severity: Literal["low", "medium", "high", "critical"],
        related_reference: str | None = None,
        supporting_evidence: list[str] | None = None,
    ) -> dict[str, Any]:
        """Prepare an escalation draft. Does not create or send a ticket."""

        result = await executor.execute(
            tool_name=ESCALATION_TOOL_NAME,
            arguments={
                "issue_summary": issue_summary,
                "severity": severity,
                "related_reference": related_reference,
                "supporting_evidence": supporting_evidence or [],
            },
            context=context,
        )

        return result
