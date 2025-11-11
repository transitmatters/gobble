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


def write_event(event: dict, agency: str = "MBTA"):
    if agency == "MBTA":
        dirname = DATA_DIR / pathlib.Path(
            output_dir_path(
                event["route_id"],
                event["direction_id"],
                event["stop_id"],
                event["event_time"],
            )
        )
    else:
        dirname = (
            DATA_DIR
            / agency
            / pathlib.Path(
                output_dir_path(
                    event["route_id"],
                    event["direction_id"],
                    event["stop_id"],
                    event["event_time"],
                )
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
