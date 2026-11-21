from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from voiceops.agents.state import AgentName, AgentStatus, VoiceOpsState


class AgentResultOutput(BaseModel):
    """Validates the output returned by an individual specialist."""

    model_config = ConfigDict(extra="forbid")

    status: AgentStatus
    summary: str
    data: dict[str, Any]


class StructuredAgentResult(BaseModel):
    """Associates a validated result with its specialist."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    status: AgentStatus
    summary: str
    data: dict[str, Any]


class StructuredEvidence(BaseModel):
    """Validates evidence returned by a specialist."""

    model_config = ConfigDict(extra="forbid")

    source: str
    description: str
    data: dict[str, Any]


class ConsolidatedResponse(BaseModel):
    """Structured response containing all investigation results."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "partial", "failed", "not_required"]
    answer: str
    agent_results: list[StructuredAgentResult]
    evidence: list[StructuredEvidence]
    errors: list[str]


RESULT_KEYS = {
    "inventory": "inventory_result",
    "order": "order_result",
    "shipment": "shipment_result",
}


def consolidate_agent_outputs(
    state: VoiceOpsState,
) -> dict[str, Any]:
    """Validate and consolidate specialist results, evidence, and errors."""

    selected_agents = state.get("selected_agents", [])
    agent_results: list[StructuredAgentResult] = []
    errors = [
        error for error in state.get("errors", []) if isinstance(error, str) and error.strip()
    ]

    # Validate each selected specialist's result.
    for agent_name in selected_agents:
        raw_result = state.get(RESULT_KEYS[agent_name])

        try:
            validated_result = AgentResultOutput.model_validate(raw_result)
        except ValidationError:
            validated_result = AgentResultOutput(
                status="failed",
                summary=(
                    f"The {agent_name} investigation did not return a valid structured result."
                ),
                data={},
            )
            errors.append(f"The {agent_name} agent returned an invalid result.")
        except (TypeError, ValueError):
            validated_result = AgentResultOutput(
                status="failed",
                summary=(
                    f"The {agent_name} investigation did not return a valid structured result."
                ),
                data={},
            )
            errors.append(f"The {agent_name} agent returned an invalid result.")

        agent_results.append(
            StructuredAgentResult(
                agent=agent_name,
                **validated_result.model_dump(),
            )
        )

    # Validate and retain evidence from all completed investigations.
    evidence: list[StructuredEvidence] = []

    for index, raw_evidence in enumerate(state.get("evidence", [])):
        try:
            evidence_item = StructuredEvidence.model_validate(raw_evidence)
        except (ValidationError, TypeError, ValueError):
            errors.append(f"Evidence item {index + 1} was invalid and was omitted.")
            continue

        evidence.append(evidence_item)

    # Determine the overall investigation status.
    if not selected_agents:
        overall_status = "not_required"
        answer = (
            "I couldn't determine which operational information you need. "
            "Please ask about inventory, an order, or a shipment."
        )
    else:
        successful_count = sum(result.status == "success" for result in agent_results)

        if successful_count == len(agent_results):
            overall_status = "success"
        elif successful_count > 0:
            overall_status = "partial"
        else:
            overall_status = "failed"

        if not agent_results:
            answer = "I couldn't complete the requested operational investigation."
        else:
            answer = "\n".join(
                f"- {result.agent.capitalize()} ({result.status}): {result.summary}"
                for result in agent_results
            )

    # Remove duplicate error messages without changing their order.
    errors = list(dict.fromkeys(errors))

    response = ConsolidatedResponse(
        status=overall_status,
        answer=answer,
        agent_results=agent_results,
        evidence=evidence,
        errors=errors,
    )

    return response.model_dump(mode="json")
