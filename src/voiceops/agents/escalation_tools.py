
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutor
from voiceops.harness.policy_engine import PolicyEngine, ToolPolicy
from voiceops.harness.tool_registry import ToolDefinition, ToolRegistry

ESCALATION_TOOL_NAME = "prepare_escalation_draft"


class EscalationToolArguments(BaseModel):
    """Validated information required to prepare an escalation draft."""

    model_config = ConfigDict(extra="forbid")

    issue_summary: str = Field(min_length=10, max_length=1000)
    severity: Literal["low", "medium", "high", "critical"]
    related_reference: str | None = Field(default=None, max_length=100)
    supporting_evidence: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    @field_validator("issue_summary", "related_reference")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Text cannot be empty.")

        return value

    @field_validator("supporting_evidence")
    @classmethod
    def clean_evidence(cls, value: list[str]) -> list[str]:
        cleaned_evidence = []

        for item in value:
            item = item.strip()

            if not item:
                raise ValueError("Supporting evidence cannot contain empty items.")

            cleaned_evidence.append(item)

        return cleaned_evidence


def prepare_escalation_draft(
    *,
    issue_summary: str,
    severity: str,
    related_reference: str | None,
    supporting_evidence: list[str],
) -> dict[str, Any]:
    """Prepare an escalation draft without creating or sending a ticket."""

    return {
        "status": "draft",
        "issue_summary": issue_summary,
        "severity": severity,
        "related_reference": related_reference,
        "supporting_evidence": supporting_evidence,
        "approval_required": True,
        "execution_status": "not_executed",
        "message": (
            "Escalation draft prepared successfully. "
            "Human approval is required before any action is taken."
        ),
    }


def create_escalation_executor(
    context: ExecutionContext,
) -> ToolExecutor:
    """Create a harness executor for escalation draft preparation."""

    registry = ToolRegistry()

    def escalation_handler(
        *,
        issue_summary: str,
        severity: str,
        related_reference: str | None = None,
        supporting_evidence: list[str] | None = None,
    ) -> dict[str, Any]:
        return prepare_escalation_draft(
            issue_summary=issue_summary,
            severity=severity,
            related_reference=related_reference,
            supporting_evidence=supporting_evidence or [],
        )

    registry.register(
        ToolDefinition(
            name=ESCALATION_TOOL_NAME,
            description=(
                "Prepare a structured escalation draft from user-provided "
                "issue details and evidence. Does not create or send a ticket."
            ),
            args_schema=EscalationToolArguments,
            handler=escalation_handler,
            requires_idempotency=False,
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        ESCALATION_TOOL_NAME,
        ToolPolicy(
            allowed_roles=frozenset(
                {
                    "admin",
                    "warehouse_manager",
                    "operator",
                    "analyst",
                }
            ),
            requires_warehouse_access=False,
        ),
    )

    return ToolExecutor(
        registry=registry,
        policy_engine=policy_engine,
    )
