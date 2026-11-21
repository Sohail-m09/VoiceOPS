
import json
import logging
from io import StringIO

from voiceops.harness.logging_manager import (
    StructuredJsonFormatter,
    configure_logging,
)


def test_structured_formatter_returns_valid_json():
    formatter = StructuredJsonFormatter()

    record = logging.LogRecord(
        name="voiceops.harness",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Tool execution succeeded",
        args=(),
        exc_info=None,
    )

    record.event = "tool_execution_succeeded"
    record.request_id = "request-123"
    record.user_id = "user-123"
    record.tool_name = "get_inventory"
    record.status = "success"
    record.duration_ms = 125.5

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["event"] == "tool_execution_succeeded"
    assert data["request_id"] == "request-123"
    assert data["user_id"] == "user-123"
    assert data["tool_name"] == "get_inventory"
    assert data["status"] == "success"
    assert data["duration_ms"] == 125.5
    assert "timestamp" in data


def test_formatter_does_not_include_unapproved_fields():
    formatter = StructuredJsonFormatter()

    record = logging.LogRecord(
        name="voiceops.harness",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Tool execution started",
        args=(),
        exc_info=None,
    )

    record.event = "tool_execution_started"
    record.password = "secret-password"
    record.access_token = "secret-token"

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["event"] == "tool_execution_started"
    assert "password" not in data
    assert "access_token" not in data


def test_configure_logging_outputs_json():
    stream = StringIO()

    logger = configure_logging(
        logger_name="voiceops.test",
        stream=stream,
    )

    logger.info(
        "Test log",
        extra={
            "event": "test_event",
            "status": "success",
        },
    )

    output = stream.getvalue()
    data = json.loads(output)

    assert data["message"] == "Test log"
    assert data["event"] == "test_event"
    assert data["status"] == "success"
