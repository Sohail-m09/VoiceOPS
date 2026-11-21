
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["admin", "warehouse_manager", "operator", "analyst"]


class ExecutionContext(BaseModel):
    """Stores the trusted context for a single agent execution."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID | None = None

    user_id: UUID
    user_role: UserRole
    warehouse_ids: tuple[UUID, ...] = ()

    request_text: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )

    @field_validator("request_text")
    @classmethod
    def validate_request_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Request text cannot be empty.")

        return value

    @field_validator("warehouse_ids")
    @classmethod
    def validate_warehouse_ids(
        cls, value: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate warehouse IDs are not allowed.")

        return value


class ContextManager:
    """Creates execution contexts from trusted request information."""

    @staticmethod
    def create_context(
        *,
        user_id: UUID,
        user_role: UserRole,
        warehouse_ids: tuple[UUID, ...] = (),
        request_text: str,
        conversation_id: UUID | None = None,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            user_id=user_id,
            user_role=user_role,
            warehouse_ids=warehouse_ids,
            request_text=request_text,
            conversation_id=conversation_id,
            metadata=metadata or {},
        )
