import csv
import os
import pathlib
from datetime import datetime, timedelta
from util import output_dir_path
from ddtrace import tracer

from config import CONFIG
from logger import set_up_logging


logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

CSV_FILENAME = "events.csv"
CSV_FIELDS = [
    "service_date",
    "route_id",
    "trip_id",
    "direction_id",
    "stop_id",
    "stop_sequence",
    "vehicle_id",
    "vehicle_label",
    "event_type",
    "event_time",
    "scheduled_headway",
    "scheduled_tt",
]
DATA_DIR = pathlib.Path("data")
STATE_FILENAME = "state.json"


def write_event(event: dict):
    dirname = DATA_DIR / pathlib.Path(
        output_dir_path(
            event["route_id"],
            event["direction_id"],
            event["stop_id"],
            event["event_time"],
        )
    )
    dirname.mkdir(parents=True, exist_ok=True)
    pathname = dirname / CSV_FILENAME
    file_exists = os.path.isfile(pathname)
    with pathname.open("a") as fd:
        writer = csv.DictWriter(fd, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(event)


def cleanup_old_files():
    """Delete CSV files older than 6 months."""
    logger.info("Starting cleanup of old files")
    cutoff_date = datetime.now() - timedelta(days=180)  # 6 months

    for root, _, files in os.walk(DATA_DIR):
        for file in files:
            if file == CSV_FILENAME:
                file_path = pathlib.Path(root) / file
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path}: {e}")

    logger.info("Completed cleanup of old files")
