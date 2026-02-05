"""Disk I/O operations for writing transit events to CSV files.

This module handles persisting processed transit events to the local filesystem.
Events are organized into directories by route, direction, and stop, with each
directory containing a single events.csv file.

Attributes:
    CSV_FILENAME: Name of the CSV file used to store events.
    CSV_FIELDS: List of field names included in the event CSV files.
    DATA_DIR: Base directory path for storing event data.
    STATE_FILENAME: Name of the state persistence file.
"""

import csv
import os
import pathlib
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
    "vehicle_consist",
    "occupancy_status",
    "occupancy_percentage",
]
DATA_DIR = pathlib.Path("data")
STATE_FILENAME = "state.json"


def write_event(event: dict):
    """Write a transit event to a CSV file on disk.

    Appends the event to an events.csv file in a directory structure organized
    by route, direction, stop, and date. Creates the directory and file with
    headers if they don't exist.

    Args:
        event: Dictionary containing event data with keys matching CSV_FIELDS.
            Must include 'route_id', 'direction_id', 'stop_id', and 'event_time'.
    """
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
