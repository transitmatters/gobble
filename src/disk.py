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

# Number of days to retain event files before cleanup
FILE_RETENTION_DAYS = CONFIG.get("file_retention_days", 180)

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


def _scan_and_cleanup(path: pathlib.Path, cutoff: datetime) -> int:
    """Recursively scan directory and delete CSV files older than cutoff.

    Args:
        path: Directory path to scan
        cutoff: Datetime cutoff - files modified before this will be deleted

    Returns:
        Number of files deleted
    """
    deleted = 0
    with os.scandir(path) as it:
        for entry in it:
            try:
                if entry.is_dir(follow_symlinks=False):
                    deleted += _scan_and_cleanup(entry.path, cutoff)
                elif entry.is_file(follow_symlinks=False) and entry.name == CSV_FILENAME:
                    if datetime.fromtimestamp(entry.stat().st_mtime) < cutoff:
                        os.unlink(entry.path)
                        deleted += 1
                        logger.info(f"Deleted old file: {entry.path}")
            except Exception as e:
                logger.warning(f"Skipping {entry.path}: {e}")
    return deleted


def cleanup_old_files(reference_time: datetime = None):
    """Delete CSV files older than the configured retention period.

    Args:
        reference_time: The datetime to use as reference for calculating cutoff.
                       Defaults to current time if not provided.
    """
    logger.info("Starting cleanup of old files")
    if reference_time is None:
        reference_time = datetime.now()
    cutoff = reference_time - timedelta(days=FILE_RETENTION_DAYS)

    deleted = _scan_and_cleanup(DATA_DIR, cutoff)
    logger.info(f"Completed cleanup — deleted {deleted} file(s)")
