import csv
import json
import pathlib
from util import output_dir_path
from ddtrace import tracer

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


@tracer.wrap()
def write_event(event):
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
    with pathname.open("a") as fd:
        writer = csv.DictWriter(fd, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writerow(event)


@tracer.wrap()
def read_state():
    pathname = pathlib.Path(DATA_DIR) / STATE_FILENAME
    try:
        with pathname.open() as fd:
            return json.load(fd)
    except FileNotFoundError:
        return {}


@tracer.wrap()
def write_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pathname = pathlib.Path(DATA_DIR) / STATE_FILENAME

    with pathname.open("w") as fd:
        json.dump(state, fd, default=str)
