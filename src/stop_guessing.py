from datetime import datetime
import pandas as pd
from typing import Dict, List, Optional

# a data structure of negligent vehicles.
# purge this on a new service date. should this be a daily cache? dynamodb? also route shapes

cache_key_fmt = "{vehicle_label}_{trip_id}"
OUTAGES_BY_VEHICLE_AND_TRIP: Dict[str, List[Dict]] = {}

SAME_OUTAGE_TIMEDELTA = datetime.timedelta(seconds=30)
LONG_OUTAGE_TIMEDELTA = datetime.timedelta(minutes=1)


def _add_update_to_sequence(cache_key: str, update: Dict) -> None:
    OUTAGES_BY_VEHICLE_AND_TRIP[cache_key].append(update)


def _remove(cache_key: str) -> None:
    OUTAGES_BY_VEHICLE_AND_TRIP[cache_key] = []


def attempt_enrich_update(update: Dict) -> Optional[Dict]:
    # if direction is none, attempt pull from trips.txt
    # if stop is null, interpolate along shapes.txt (trip-shape relationship in trips.txt)
    #   maybe fetch and cache shape?
    #   if there are a couple of options, tie-break with the schedule?
    # if current_status is IN_TRANSIT...
    #   check previous location stamp. if its TOO CLOSE, it might be stopped.
    # if its TOO CLOSE to a stop location, its stopped at a stop.
    #   otherwise, it might clogged in traffic, sitting at a red, whatever.
    # update event_type accordingly
    return None


def report_outage(update: Dict) -> Optional[pd.DataFrame]:
    """Given an outage event, cache it and potentially try fill the missing information.
    
    If the outage duration is small (<1 minute,) it will return nothing. 
    It will then attempt to fill the missing information using shape interpolation and gtfs data
    This might still fail and return nothing. 
    """
    cache_key = cache_key_fmt.format(vehicle_label=update["vehicle_label"], trip_id=update["trip_id"])
    outage_sequence = OUTAGES_BY_VEHICLE_AND_TRIP.get(cache_key, [])
    if len(outage_sequence) == 0:
        _add_update_to_sequence(cache_key, update)
        return None

    # compare latest outage timestamp....
    last_ts = outage_sequence[-1]["updated_at"]
    first_ts = outage_sequence[0]["updated_at"]
    current_ts = update["updated_at"]

    # if timestamps are not close, remove entire cache entry. this is now the most recent instance.
    if current_ts - last_ts >= SAME_OUTAGE_TIMEDELTA:
        _remove(cache_key)
        _add_update_to_sequence(cache_key, update)
        # return empty.
        return None
    else:
        # append this event to outages and cache
        _add_update_to_sequence(cache_key, update)
        # compare first timestamp and this timestamp...
        if current_ts - first_ts <= LONG_OUTAGE_TIMEDELTA:
            # if the timedelta is < 1 minute, return empty.
            return None
        else:
            # else, attempt to intuit the stop information via shapes and trip info
            return attempt_enrich_update(update)
