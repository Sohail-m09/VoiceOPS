
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for tool execution retries and timeouts."""

    max_attempts: int = 3
    delay_seconds: float = 0.5
    timeout_seconds: float = 10.0
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("Maximum attempts must be at least 1.")

        if self.delay_seconds < 0:
            raise ValueError("Retry delay cannot be negative.")

        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than zero.")

        if not self.retryable_exceptions:
            raise ValueError("At least one retryable exception is required.")

        if not all(
            isinstance(error, type) and issubclass(error, Exception)
            for error in self.retryable_exceptions
        ):
            raise ValueError(
                "Retryable exceptions must be Exception subclasses."
            )


class RetryManager:
    """Manages retries and timeouts for asynchronous operations."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()

    async def run(
        self,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute an operation with configured retries and timeouts."""

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await asyncio.wait_for(
                    operation(),
                    timeout=self.config.timeout_seconds,
                )

            except Exception as exc:
                should_retry = isinstance(
                    exc,
                    self.config.retryable_exceptions,
                )

                if not should_retry or attempt == self.config.max_attempts:
                    raise

                await asyncio.sleep(self.config.delay_seconds)

        raise RuntimeError("Retry execution ended unexpectedly.")
