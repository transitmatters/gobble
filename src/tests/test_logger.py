import json
import logging
import logging.handlers
import os
import pathlib
import subprocess
import sys

import pytest

from logger import LOG_BACKUP_COUNT, LOG_MAX_BYTES, configure_logging, set_up_logging

SRC_DIR = pathlib.Path(__file__).resolve().parents[1]


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


def _added_handlers(root: logging.Logger, before: list) -> list:
    return [h for h in root.handlers if h not in before]


def _flush(root: logging.Logger) -> None:
    for handler in root.handlers:
        handler.flush()


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
    _flush(root_logger)

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2, "a traceback must stay inside its record's line"
    info, error = (json.loads(line) for line in lines)

    assert info["status"] == "INFO"
    assert info["message"] == "hello"
    assert info["logger.name"] == "gobble_test"
    assert "logger.thread_name" in info
    assert "timestamp" in info
    assert "taskName" not in info

    assert error["status"] == "ERROR"
    assert error["message"] == "boom"
    assert "Traceback (most recent call last)" in error["error.stack"]
    assert "ZeroDivisionError" in error["error.stack"]


def test_level_can_be_set_by_name(tmp_path, root_logger):
    """The entry points pass config's log_level, a name like "debug", to turn the per-event lines back on"""
    log_path = tmp_path / "gobble.log"
    configure_logging(log_path, "debug")

    set_up_logging("gobble_test").debug("per-event line")
    _flush(root_logger)

    assert json.loads(log_path.read_text())["status"] == "DEBUG"


def test_file_rotates_and_stderr_only_gets_warnings(tmp_path, root_logger):
    before = root_logger.handlers[:]
    configure_logging(tmp_path / "gobble.log")

    added = _added_handlers(root_logger, before)
    [file_handler] = [h for h in added if isinstance(h, logging.handlers.RotatingFileHandler)]
    [stream_handler] = [h for h in added if not isinstance(h, logging.FileHandler)]
    assert file_handler.maxBytes == LOG_MAX_BYTES
    assert file_handler.backupCount == LOG_BACKUP_COUNT
    assert file_handler.level == logging.NOTSET
    assert stream_handler.level == logging.WARNING


def test_set_up_logging_adds_no_handlers():
    """Records propagate to the root logger's handlers, so module loggers must not add their own"""
    logger = set_up_logging("gobble_test_no_handlers")
    assert logger.handlers == []
    assert logger.propagate


def test_importing_entry_points_sets_up_no_logging():
    """Only running gobble.py or s3_upload.py sets up logging; importing them (as tests do) must not write a log.

    Runs in a subprocess: pytest already gives the root logger handlers, which would make a stray
    logging.basicConfig() a silent no-op here.
    """
    script = f"""
import logging, sys
sys.path.insert(0, {str(SRC_DIR)!r})
import gobble, s3_upload
print(len(logging.getLogger().handlers))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=SRC_DIR.parent,  # config.py reads config/local.json relative to the repo root
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip().splitlines()[-1] == "0"


def test_ddtrace_injects_trace_ids(tmp_path):
    """#63: with the tracer on, a record logged inside a span carries that span's IDs.

    Runs in a subprocess, so the tracer it turns on (and patching logging) doesn't leak into other tests.
    """
    log_path = tmp_path / "gobble.log"
    script = f"""
import json, sys
sys.path.insert(0, {str(SRC_DIR)!r})
from ddtrace import patch, tracer
patch(logging=True)
from logger import configure_logging, set_up_logging
configure_logging({str(log_path)!r})
tracer.enabled = True
with tracer.trace("test.span") as span:
    set_up_logging("gobble_test").info("traced")
print(json.dumps({{"span_id": str(span.span_id)}}))
"""
    env = {
        **os.environ,
        # Nothing listens here; the span just fails to send when the process exits
        "DD_TRACE_AGENT_URL": "http://127.0.0.1:9",
        "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
        "DD_REMOTE_CONFIGURATION_ENABLED": "false",
    }
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=60, check=True
    )
    span_id = json.loads(result.stdout.strip().splitlines()[-1])["span_id"]

    [record] = [json.loads(line) for line in log_path.read_text().splitlines() if '"traced"' in line]
    assert record["dd.span_id"] == span_id
    assert record["dd.trace_id"] not in ("", "0")
