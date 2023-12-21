from datetime import date, datetime
from typing import Tuple
import pandas as pd
import logging
from ddtrace import tracer
import warnings

from constants import STOPS
import gtfs
import disk
import util

logger = logging.getLogger(__name__)

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
    return stops_df[stops_df["stop_id"] == stop_id].iloc[0].stop_name


def arr_or_dep_event(prev, current_status, current_stop_sequence, event_type: str, stop_id) -> Tuple[bool, bool]:
    is_departure_event = prev["stop_id"] != stop_id and prev["stop_sequence"] < current_stop_sequence
    is_arrival_event = current_status == "STOPPED_AT" and prev.get("event_type", event_type) == "DEP"
    return is_departure_event, is_arrival_event


def reduce_update_event(update):
    current_status = update["attributes"]["current_status"]
    event_type = EVENT_TYPE_MAP[current_status]
    updated_at = datetime.fromisoformat(update["attributes"]["updated_at"])
    return (
        current_status,
        event_type,
        update["attributes"]["current_stop_sequence"],
        update["attributes"]["direction_id"],
        update["relationships"]["route"]["data"]["id"],
        update["relationships"]["stop"]["data"]["id"],
        update["relationships"]["trip"]["data"]["id"],
        update["attributes"]["label"],
        updated_at,
    )


@tracer.wrap()
def process_event(
    update,
    current_stop_state,
    gtfs_service_date: date,
    scheduled_trips: pd.DataFrame,
    scheduled_stop_times: pd.DataFrame,
    stops: pd.DataFrame,
):
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

        stop_name = get_stop_name(stops, stop_id)
        service_date = util.service_date(updated_at)

        # refresh the gtfs data bundle if the day has incremented
        if gtfs_service_date != service_date:
            logger.info(f"Refreshing GTFS bundle from {gtfs_service_date} to {service_date}...")
            gtfs_service_date = service_date
            scheduled_trips, scheduled_stop_times, stops = gtfs.read_gtfs(gtfs_service_date)

        if stop_id in STOPS.get(route_id, {}):
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

            event = enrich_event(df, scheduled_trips, scheduled_stop_times)
            disk.write_event(event)

    current_stop_state[trip_id] = {
        "stop_sequence": current_stop_sequence,
        "stop_id": stop_id,
        "updated_at": updated_at,
        "event_type": event_type,
    }

    # write the state out here
    disk.write_state(current_stop_state)


def enrich_event(df: pd.DataFrame, scheduled_trips: pd.DataFrame, scheduled_stop_times: pd.DataFrame):
    """
    Given a dataframe with a single event, enrich it with headway information and return a single event dict
    """
    # ensure timestamp is always in local time to match the rest of the data
    df["event_time"] = df["event_time"].dt.tz_convert("US/Eastern")
    
    headway_adjusted_df = gtfs.add_gtfs_headways(df, scheduled_trips, scheduled_stop_times)
    # future warning: returning a series is actually the correct future behavior of to_pydatetime(), can drop the
    # context manager later
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=FutureWarning)
        headway_adjusted_df["event_time"] = pd.Series(
            headway_adjusted_df["event_time"].dt.to_pydatetime(), dtype="object"
        )
    # TODO: more explicit datetime string conversion?
    event = headway_adjusted_df.to_dict("records")[0]
    return event
