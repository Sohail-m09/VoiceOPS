from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Request body for a VoiceOps chat message."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty.")

        return value


class ChatResponse(BaseModel):
    """Public response returned after an agent investigation."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    conversation_id: UUID

    status: Literal["success", "partial", "failed", "not_required"]
    answer: str
    clarification_required: bool = False

    agent_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    errors: list[str]
