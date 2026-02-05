"""Logging configuration for Gobble.

This module provides centralized logging setup with JSON formatting for
compatibility with Datadog log aggregation and parsing.
"""

import logging
from pythonjsonlogger import jsonlogger


def set_up_logging(name: str):
    """Configure and return a logger with JSON formatting.

    Creates a logger that outputs logs in JSON format, which enables proper
    parsing of multi-line logs (such as stack traces) by Datadog.

    Args:
        name: The name for the logger, typically __name__ of the calling module.

    Returns:
        A configured logging.Logger instance with JSON formatting enabled.
    logger = logging.getLogger(name)
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    return logger
