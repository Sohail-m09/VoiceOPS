
from uuid import uuid4

import pytest

from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.pause_resume_manager import (
    CheckpointAlreadyExistsError,
    CheckpointNotFoundError,
    ExecutionStatus,
    InvalidExecutionStateError,
    PauseResumeManager,
)


def create_context() -> ExecutionContext:
    return ExecutionContext(
        user_id=uuid4(),
        user_role="operator",
        request_text="Check warehouse inventory",
    )


def test_register_creates_running_checkpoint():
    manager = PauseResumeManager()
    context = create_context()

    checkpoint = manager.register(context)

    assert checkpoint.request_id == context.request_id
    assert checkpoint.status == ExecutionStatus.RUNNING
    assert checkpoint.created_at is not None
    assert checkpoint.updated_at is not None


def test_duplicate_checkpoint_registration_is_rejected():
    manager = PauseResumeManager()
    context = create_context()

    manager.register(context)

    with pytest.raises(CheckpointAlreadyExistsError):
        manager.register(context)


def test_get_returns_registered_checkpoint():
    manager = PauseResumeManager()
    context = create_context()

    registered = manager.register(context)
    retrieved = manager.get(context.request_id)

    assert retrieved == registered


def test_missing_checkpoint_is_rejected():
    manager = PauseResumeManager()

    with pytest.raises(CheckpointNotFoundError):
        manager.get(uuid4())


def test_pause_running_execution():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    checkpoint = manager.pause(
        context.request_id,
        "Waiting for additional information",
    )

    assert checkpoint.status == ExecutionStatus.PAUSED
    assert checkpoint.pause_reason == (
        "Waiting for additional information"
    )
    assert checkpoint.paused_at is not None


def test_empty_pause_reason_is_rejected():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    with pytest.raises(ValueError, match="Pause reason"):
        manager.pause(context.request_id, "   ")


def test_resume_paused_execution():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    manager.pause(context.request_id, "Waiting for input")

    checkpoint = manager.resume(context.request_id)

    assert checkpoint.status == ExecutionStatus.RESUMED
    assert checkpoint.resumed_at is not None
    assert checkpoint.pause_reason == "Waiting for input"


def test_running_execution_cannot_be_resumed():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    with pytest.raises(InvalidExecutionStateError):
        manager.resume(context.request_id)


def test_paused_execution_cannot_be_paused_again():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    manager.pause(context.request_id, "Waiting for input")

    with pytest.raises(InvalidExecutionStateError):
        manager.pause(context.request_id, "Another reason")


def test_resumed_execution_can_be_paused_again():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    manager.pause(context.request_id, "Waiting for input")
    manager.resume(context.request_id)

    checkpoint = manager.pause(
        context.request_id,
        "Waiting for another event",
    )

    assert checkpoint.status == ExecutionStatus.PAUSED
    assert checkpoint.pause_reason == "Waiting for another event"


def test_resumed_execution_can_be_completed():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    manager.pause(context.request_id, "Waiting for input")
    manager.resume(context.request_id)

    checkpoint = manager.complete(context.request_id)

    assert checkpoint.status == ExecutionStatus.COMPLETED
    assert checkpoint.completed_at is not None


def test_running_execution_can_be_completed():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    checkpoint = manager.complete(context.request_id)

    assert checkpoint.status == ExecutionStatus.COMPLETED


def test_paused_execution_cannot_be_completed():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)

    manager.pause(context.request_id, "Waiting for input")

    with pytest.raises(InvalidExecutionStateError):
        manager.complete(context.request_id)


def test_completed_execution_cannot_be_resumed():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)
    manager.complete(context.request_id)

    with pytest.raises(InvalidExecutionStateError):
        manager.resume(context.request_id)


def test_completed_execution_cannot_be_paused():
    manager = PauseResumeManager()
    context = create_context()
    manager.register(context)
    manager.complete(context.request_id)

    with pytest.raises(InvalidExecutionStateError):
        manager.pause(context.request_id, "Waiting for input")
