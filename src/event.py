import json
from datetime import datetime
from typing import Tuple
import pandas as pd
from ddtrace import tracer
import warnings

from config import CONFIG
from constants import BUS_STOPS, ROUTES_CR, ROUTES_RAPID
import disk
import gtfs
from logger import set_up_logging
import util

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


EVENT_TYPE_MAP = {
    # use the first instance of this signal as departure
    "IN_TRANSIT_TO": "DEP",
    # use the first instance of this signal as arrival
    "STOPPED_AT": "ARR",
    # this signal exists in theory but isnt used in practice in the realtime v3 API.
    # we include it for completeness and in case it is ever used
    "INCOMING_AT": "ARR",
}


def get_stop_name(stops_df: pd.DataFrame, stop_id: str) -> str:
    matching_stops = stops_df[stops_df["stop_id"] == stop_id]
    if len(matching_stops) > 0:
        return matching_stops.iloc[0].stop_name
    else:
        # TODO: An example of this would be stop id ER-0117-01, which was the Lynn Interim stop on the Newburyport/Rockport Line
        # We just use this name for logging purposes so its NBD if we return a raw id.
        logger.error(f"Encountered stop id {stop_id} without human-readable name. Is this a temporary stop?")
        return stop_id


def arr_or_dep_event(
    prev: dict, current_status: str, current_stop_sequence: int, event_type: str, stop_id: str
) -> Tuple[bool, bool]:
    is_departure_event = prev["stop_id"] != stop_id and prev["stop_sequence"] < current_stop_sequence
    is_arrival_event = current_status == "STOPPED_AT" and prev.get("event_type", event_type) == "DEP"
    return is_departure_event, is_arrival_event


def reduce_update_event(update: dict) -> Tuple:
    current_status = update["attributes"]["current_status"]
    event_type = EVENT_TYPE_MAP[current_status]
    updated_at = datetime.fromisoformat(update["attributes"]["updated_at"])

    try:
        # The vehicle’s current (when current_status is STOPPED_AT) or next stop.
        stop_id = update["relationships"]["stop"]["data"]["id"]
    except (TypeError, KeyError):
        logger.error(f"Encountered degenerate stop information. This event will be skipped: {json.dumps(update)}")
        stop_id = None

    return (
        current_status,
        event_type,
        update["attributes"]["current_stop_sequence"],
        update["attributes"]["direction_id"],
        update["relationships"]["route"]["data"]["id"],
        stop_id,
        update["relationships"]["trip"]["data"]["id"],
        update["attributes"]["label"],
        updated_at,
    )


@tracer.wrap()
def process_event(update: dict, current_stop_state: dict):
    """Process a single event from the MBTA's realtime API."""
    (
        current_status,
        event_type,
        current_stop_sequence,
        direction_id,
        route_id,
        stop_id,
        trip_id,
        vehicle_label,
        updated_at,
    ) = reduce_update_event(update)

    prev = current_stop_state.get(
        trip_id,
        {
            "stop_sequence": current_stop_sequence,
            "stop_id": stop_id,
            "updated_at": updated_at,
            "event_type": event_type,
        },
    )

    # current_stop_state updated_at is isofmt str, not datetime.
    if isinstance(prev["updated_at"], str):
        prev["updated_at"] = datetime.fromisoformat(prev["updated_at"])

    if stop_id is None:
        # TODO (hamima): attempt to enrich update with stop information. if successful,
        # continue. otherwise, return.
        return

    is_departure_event, is_arrival_event = arr_or_dep_event(
        prev=prev,
        current_status=current_status,
        current_stop_sequence=current_stop_sequence,
        event_type=event_type,
        stop_id=stop_id,
    )

    if is_departure_event or is_arrival_event:
        if is_departure_event:
            stop_id = prev["stop_id"]

        gtfs_archive = gtfs.get_current_gtfs_archive()
        stop_name = get_stop_name(gtfs_archive.stops, stop_id)
        service_date = util.service_date(updated_at)

        # store all commuter rail/subway stops, but only some bus stops
        if route_id in ROUTES_CR.union(ROUTES_RAPID) or stop_id in BUS_STOPS.get(route_id, {}):
            logger.info(
                f"[{updated_at.isoformat()}] Event: route={route_id} trip_id={trip_id} {event_type} stop={stop_name}"
            )

            # write the event here
            df = pd.DataFrame(
                [
                    {
                        "service_date": service_date,
                        "route_id": route_id,
                        "trip_id": trip_id,
                        "direction_id": direction_id,
                        "stop_id": stop_id,
                        "stop_sequence": current_stop_sequence,
                        "vehicle_id": "0",  # TODO??
                        "vehicle_label": vehicle_label,
                        "event_type": event_type,
                        "event_time": updated_at,
                    }
                ],
                index=[0],
            )

            event = enrich_event(df, gtfs_archive)
            disk.write_event(event)

    current_stop_state[trip_id] = {
        "stop_sequence": current_stop_sequence,
        "stop_id": stop_id,
        "updated_at": updated_at,
        "event_type": event_type,
    }

    # write the state out here
    disk.write_state(current_stop_state)


def enrich_event(df: pd.DataFrame, gtfs_archive: gtfs.GtfsArchive):
    """
    Given a dataframe with a single event, enrich it with headway information and return a single event dict
    """
    # ensure timestamp is always in local time to match the rest of the data
    df["event_time"] = df["event_time"].dt.tz_convert(util.EASTERN_TIME)

    # get trips and stop times for this route specifically (slow to scan them all)
    route_id = df["route_id"].iloc[0]
    scheduled_trips_for_route = gtfs_archive.trips_by_route_id(route_id)
    scheduled_stop_times_for_route = gtfs_archive.stop_times_by_route_id(route_id)

    headway_adjusted_df = gtfs.add_gtfs_headways(df, scheduled_trips_for_route, scheduled_stop_times_for_route)
    # future warning: returning a series is actually the correct future behavior of to_pydatetime(), can drop the
    # context manager later
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=FutureWarning)
        headway_adjusted_df["event_time"] = pd.Series(
            headway_adjusted_df["event_time"].dt.to_pydatetime(), dtype="object"
        )

    event = headway_adjusted_df.to_dict("records")[0]
    return event
