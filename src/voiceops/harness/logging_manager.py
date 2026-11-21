
import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        allowed_fields = (
            "event",
            "request_id",
            "user_id",
            "tool_name",
            "status",
            "duration_ms",
            "error_type",
        )

        for field in allowed_fields:
            value = getattr(record, field, None)

            if value is not None:
                log_data[field] = value

        return json.dumps(log_data, default=str)


def configure_logging(
    level: int = logging.INFO,
    logger_name: str = "voiceops.harness",
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure structured JSON logging for the agent harness."""

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.StreamHandler(
        stream if stream is not None else sys.stdout
    )
    handler.setFormatter(StructuredJsonFormatter())

    logger.addHandler(handler)

    return logger
