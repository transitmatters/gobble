import json
import logging

import pytest

from logger import configure_logging, set_up_logging


@pytest.fixture
def root_logger():
    """Restore the root logger's handlers and level after configure_logging changes them"""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield root
    for handler in root.handlers[:]:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


def test_writes_one_json_line_per_record(tmp_path, root_logger):
    log_path = tmp_path / "gobble.log"
    configure_logging(log_path)
    logger = set_up_logging("gobble_test")

    logger.debug("not written at INFO")
    logger.info("hello")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("boom")
    for handler in root_logger.handlers:
        handler.flush()

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2, "a traceback must stay inside its record's line"
    info, error = (json.loads(line) for line in lines)

    assert info["status"] == "INFO"
    assert info["message"] == "hello"
    assert info["logger.name"] == "gobble_test"
    assert "logger.thread_name" in info
    assert "timestamp" in info

    assert error["status"] == "ERROR"
    assert error["message"] == "boom"
    assert "Traceback (most recent call last)" in error["error.stack"]
    assert "ZeroDivisionError" in error["error.stack"]


def test_record_extras_are_written(tmp_path, root_logger):
    """ddtrace's log injection adds dd.* attributes to each record; they must reach the JSON for #63"""
    log_path = tmp_path / "gobble.log"
    configure_logging(log_path)

    set_up_logging("gobble_test").info("traced", extra={"dd.trace_id": "123", "dd.span_id": "456"})
    for handler in root_logger.handlers:
        handler.flush()

    record = json.loads(log_path.read_text())
    assert record["dd.trace_id"] == "123"
    assert record["dd.span_id"] == "456"


def test_set_up_logging_adds_no_handlers():
    """Records propagate to the root logger's handlers, so module loggers must not add their own"""
    logger = set_up_logging("gobble_test_no_handlers")
    assert logger.handlers == []
    assert logger.propagate
