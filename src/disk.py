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
    cutoff = datetime.now() - timedelta(days=180)
    deleted = 0

    def scan_and_cleanup(path: pathlib.Path):
        nonlocal deleted
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        scan_and_cleanup(entry.path)
                    elif entry.is_file(follow_symlinks=False) and entry.name == CSV_FILENAME:
                        if datetime.fromtimestamp(entry.stat().st_mtime) < cutoff:
                            os.unlink(entry.path)
                            deleted += 1
                            logger.info(f"Deleted old file: {entry.path}")
                except Exception as e:
                    logger.warning(f"Skipping {entry.path}: {e}")

    scan_and_cleanup(DATA_DIR)
    logger.info(f"Completed cleanup — deleted {deleted} file(s)")
