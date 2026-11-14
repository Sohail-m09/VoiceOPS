import logging

import pytest

from voiceops.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_logging_state():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_log_lines_have_time_level_name_and_message(capsys):
    configure_logging("INFO")
    logging.getLogger("voiceops.demo").info("hello")
    parts = [part.strip() for part in capsys.readouterr().err.strip().split("|")]
    assert len(parts) == 4
    assert parts[0]
    assert parts[1:] == ["INFO", "voiceops.demo", "hello"]


def test_messages_below_the_configured_level_are_hidden(capsys):
    configure_logging("WARNING")
    logger = logging.getLogger("voiceops.demo")
    logger.info("hidden message")
    logger.warning("shown message")
    output = capsys.readouterr().err
    assert "hidden message" not in output
    assert "shown message" in output


def test_exceptions_are_logged_with_a_traceback(capsys):
    configure_logging("INFO")
    try:
        1 / 0
    except ZeroDivisionError:
        logging.getLogger("voiceops.demo").exception("calculation failed")
    output = capsys.readouterr().err
    assert "ERROR" in output
    assert "calculation failed" in output
    assert "Traceback (most recent call last)" in output
    assert "ZeroDivisionError" in output
