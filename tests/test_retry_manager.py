
import asyncio

import pytest

from voiceops.harness.retry_manager import RetryConfig, RetryManager


def test_operation_succeeds_without_retry():
    manager = RetryManager(
        RetryConfig(delay_seconds=0),
    )
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        return "success"

    result = asyncio.run(manager.run(operation))

    assert result == "success"
    assert attempts == 1


def test_connection_error_is_retried():
    manager = RetryManager(
        RetryConfig(
            max_attempts=3,
            delay_seconds=0,
        )
    )
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            raise ConnectionError("Temporary connection failure.")

        return "success"

    result = asyncio.run(manager.run(operation))

    assert result == "success"
    assert attempts == 3


def test_retry_stops_after_maximum_attempts():
    manager = RetryManager(
        RetryConfig(
            max_attempts=3,
            delay_seconds=0,
        )
    )
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ConnectionError("Service unavailable.")

    with pytest.raises(ConnectionError):
        asyncio.run(manager.run(operation))

    assert attempts == 3


def test_non_retryable_exception_is_not_retried():
    manager = RetryManager(
        RetryConfig(
            max_attempts=3,
            delay_seconds=0,
        )
    )
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError("Invalid operation.")

    with pytest.raises(ValueError):
        asyncio.run(manager.run(operation))

    assert attempts == 1


def test_operation_timeout_is_enforced():
    manager = RetryManager(
        RetryConfig(
            max_attempts=3,
            delay_seconds=0,
            timeout_seconds=0.01,
        )
    )
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(0.1)

    with pytest.raises(TimeoutError):
        asyncio.run(manager.run(operation))

    assert attempts == 1


def test_maximum_attempts_must_be_positive():
    with pytest.raises(ValueError, match="at least 1"):
        RetryConfig(max_attempts=0)


def test_retry_delay_cannot_be_negative():
    with pytest.raises(ValueError, match="cannot be negative"):
        RetryConfig(delay_seconds=-1)


def test_timeout_must_be_positive():
    with pytest.raises(ValueError, match="greater than zero"):
        RetryConfig(timeout_seconds=0)


def test_retryable_exceptions_must_be_valid():
    with pytest.raises(ValueError, match="Exception subclasses"):
        RetryConfig(retryable_exceptions=(str,))


def test_retryable_exceptions_cannot_be_empty():
    with pytest.raises(ValueError, match="At least one"):
        RetryConfig(retryable_exceptions=())
