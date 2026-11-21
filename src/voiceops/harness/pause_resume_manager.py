
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from uuid import UUID

from voiceops.harness.context_manager import ExecutionContext


class ExecutionStatus(StrEnum):
    """Possible states of an agent execution."""

    RUNNING = "running"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"


class CheckpointAlreadyExistsError(Exception):
    """Raised when a checkpoint already exists."""


class CheckpointNotFoundError(Exception):
    """Raised when an execution checkpoint does not exist."""


class InvalidExecutionStateError(Exception):
    """Raised when an invalid state transition is requested."""


@dataclass(frozen=True)
class ExecutionCheckpoint:
    """Stores the current state of an agent execution."""

    request_id: UUID
    status: ExecutionStatus
    created_at: datetime
    updated_at: datetime
    pause_reason: str | None = None
    paused_at: datetime | None = None
    resumed_at: datetime | None = None
    completed_at: datetime | None = None


class PauseResumeManager:
    """Manages execution checkpoints and state transitions."""

    def __init__(self) -> None:
        self._checkpoints: dict[UUID, ExecutionCheckpoint] = {}
        self._lock = Lock()

    def register(
        self,
        context: ExecutionContext,
    ) -> ExecutionCheckpoint:
        """Register a new execution checkpoint."""

        request_id = context.request_id
        now = datetime.now(UTC)

        with self._lock:
            if request_id in self._checkpoints:
                raise CheckpointAlreadyExistsError(
                    f"Checkpoint for request '{request_id}' already exists."
                )

            checkpoint = ExecutionCheckpoint(
                request_id=request_id,
                status=ExecutionStatus.RUNNING,
                created_at=now,
                updated_at=now,
            )

            self._checkpoints[request_id] = checkpoint

            return checkpoint

    def get(
        self,
        request_id: UUID,
    ) -> ExecutionCheckpoint:
        """Retrieve an execution checkpoint."""

        with self._lock:
            return self._get_checkpoint(request_id)

    def pause(
        self,
        request_id: UUID,
        reason: str,
    ) -> ExecutionCheckpoint:
        """Pause a running or resumed execution."""

        reason = reason.strip()

        if not reason:
            raise ValueError("Pause reason cannot be empty.")

        with self._lock:
            checkpoint = self._get_checkpoint(request_id)

            if checkpoint.status not in (
                ExecutionStatus.RUNNING,
                ExecutionStatus.RESUMED,
            ):
                raise InvalidExecutionStateError(
                    f"Cannot pause an execution in "
                    f"'{checkpoint.status}' state."
                )

            now = datetime.now(UTC)

            updated = replace(
                checkpoint,
                status=ExecutionStatus.PAUSED,
                pause_reason=reason,
                paused_at=now,
                updated_at=now,
            )

            self._checkpoints[request_id] = updated

            return updated

    def resume(
        self,
        request_id: UUID,
    ) -> ExecutionCheckpoint:
        """Resume a paused execution."""

        with self._lock:
            checkpoint = self._get_checkpoint(request_id)

            if checkpoint.status != ExecutionStatus.PAUSED:
                raise InvalidExecutionStateError(
                    "Only paused executions can be resumed."
                )

            now = datetime.now(UTC)

            updated = replace(
                checkpoint,
                status=ExecutionStatus.RESUMED,
                resumed_at=now,
                updated_at=now,
            )

            self._checkpoints[request_id] = updated

            return updated

    def complete(
        self,
        request_id: UUID,
    ) -> ExecutionCheckpoint:
        """Mark a running or resumed execution as completed."""

        with self._lock:
            checkpoint = self._get_checkpoint(request_id)

            if checkpoint.status not in (
                ExecutionStatus.RUNNING,
                ExecutionStatus.RESUMED,
            ):
                raise InvalidExecutionStateError(
                    f"Cannot complete an execution in "
                    f"'{checkpoint.status}' state."
                )

            now = datetime.now(UTC)

            updated = replace(
                checkpoint,
                status=ExecutionStatus.COMPLETED,
                completed_at=now,
                updated_at=now,
            )

            self._checkpoints[request_id] = updated

            return updated

    def _get_checkpoint(
        self,
        request_id: UUID,
    ) -> ExecutionCheckpoint:
        """Retrieve a checkpoint while holding the manager lock."""

        checkpoint = self._checkpoints.get(request_id)

        if checkpoint is None:
            raise CheckpointNotFoundError(
                f"No checkpoint found for request '{request_id}'."
            )

        return checkpoint
