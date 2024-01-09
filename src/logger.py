import logging
from pythonjsonlogger import jsonlogger


def set_up_logging(name: str):
    logger = logging.getLogger(name)

    # sets up logger to handle stack traces and other multi-line logs in a way that Datadog can parse
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    return logger
