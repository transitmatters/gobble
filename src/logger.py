import logging
import logging.handlers
import os
from pythonjsonlogger import jsonlogger

# Each log file is rotated at this size and keeps this many old copies, so it can't fill the disk
LOG_MAX_BYTES = 50 * 1024 * 1024
LOG_BACKUP_COUNT = 3


class DatadogJsonFormatter(jsonlogger.JsonFormatter):
    def process_log_record(self, log_record):
        # rename_fields can't do this one: it raises KeyError on records without a traceback
        if "exc_info" in log_record:
            log_record["error.stack"] = log_record.pop("exc_info")
        return log_record


def json_formatter() -> jsonlogger.JsonFormatter:
    """One JSON object per line, so Datadog indexes each record (traceback included) as one entry with its level.

    Fields are renamed to Datadog's standard attributes. Record attributes ddtrace adds when DD_LOGS_INJECTION is
    on (dd.trace_id, dd.span_id, dd.service, dd.env, dd.version) aren't reserved, so they're written as-is and
    Datadog links the log to its trace.
    """
    return DatadogJsonFormatter(
        "%(levelname)s %(name)s %(threadName)s %(message)s",
        rename_fields={
            "levelname": "status",
            "name": "logger.name",
            "threadName": "logger.thread_name",
        },
        timestamp=True,
    )


def configure_logging(filename: str | os.PathLike, level: int = logging.INFO) -> None:
    """Send every logger's records to a rotating JSON file, which the Datadog Agent tails, and to stderr, which
    goes to the journal. Call once, from an entry point."""
    root = logging.getLogger()
    root.setLevel(level)
    formatter = json_formatter()

    file_handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    stream_handler = logging.StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.setFormatter(formatter)
        root.addHandler(handler)


def set_up_logging(name: str) -> logging.Logger:
    # Handlers live on the root logger (configure_logging), so each record is written once per handler
    return logging.getLogger(name)
