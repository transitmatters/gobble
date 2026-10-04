from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import gtfs
from event import process_event, process_remove
from trip_state import TripsStateManager

EASTERN = ZoneInfo("US/Eastern")
TRIP = "Route24Bridge-866525-6020"


def _update(trip_id, stop_id, sequence, status, at, vehicle_id="1823", route_id="CR-Kingston"):
    return {
        "id": vehicle_id,
        "attributes": {
            "current_status": status,
            "updated_at": at.isoformat(),
            "current_stop_sequence": sequence,
            "direction_id": 1,
            "label": vehicle_id,
            "carriages": [],
            "occupancy_status": None,
        },
        "relationships": {
            "stop": {"data": {"id": stop_id}},
            "route": {"data": {"id": route_id}},
            "trip": {"data": {"id": trip_id}},
        },
    }


@pytest.fixture
def written():
    """Events written to disk, with GTFS and trip state files stubbed out."""
    archive = Mock(spec=gtfs.GtfsArchive)
    archive.stops = pd.DataFrame([{"stop_id": "NEC-2287", "stop_name": "South Station"}])
    archive.trips_by_route_id.return_value = pd.DataFrame([{"trip_id": TRIP, "direction_id": 1}])
    archive.stop_times_by_route_id.return_value = pd.DataFrame(
        [
            {"trip_id": TRIP, "stop_id": "MM-0079-S", "stop_sequence": 70},
            {"trip_id": TRIP, "stop_id": "NEC-2287", "stop_sequence": 80},
        ]
    )
    events = []
    with (
        patch("event.gtfs.get_current_gtfs_archive", return_value=archive),
        patch("event.write_event", side_effect=events.append),
        patch("trip_state.write_trips_state_file"),
        patch("trip_state.read_trips_state_file", return_value=None),
    ):
        yield events


def _arrivals(events):
    return [e for e in events if e["event_type"] == "ARR"]


def _heading_to_last_stop(trips_state, at):
    # Departs Quincy Center (seq 70) heading for South Station, the trip's last stop (seq 80)
    process_event(_update(TRIP, "MM-0079-S", 70, "STOPPED_AT", at - timedelta(minutes=1)), trips_state)
    process_event(_update(TRIP, "NEC-2287", 80, "IN_TRANSIT_TO", at), trips_state)


def test_removal_after_heading_to_last_stop_is_an_arrival(written):
    trips_state = TripsStateManager()
    start = datetime(2026, 10, 3, 11, 6, tzinfo=EASTERN)
    _heading_to_last_stop(trips_state, start)

    arrived = start + timedelta(minutes=18)
    process_remove({"id": "1823", "type": "vehicle"}, trips_state, arrived)

    [arrival] = _arrivals(written)
    assert arrival["stop_id"] == "NEC-2287"
    assert arrival["event_time"] == arrived
    assert arrival["direction_id"] == 1


def test_flapping_vehicle_only_arrives_once(written):
    trips_state = TripsStateManager()
    start = datetime(2026, 10, 3, 11, 6, tzinfo=EASTERN)
    _heading_to_last_stop(trips_state, start)
    process_remove({"id": "1823", "type": "vehicle"}, trips_state, start + timedelta(minutes=18))

    # The feed brings the train back on the same trip, then drops it again
    process_event(_update(TRIP, "NEC-2287", 80, "IN_TRANSIT_TO", start + timedelta(minutes=21)), trips_state)
    process_remove({"id": "1823", "type": "vehicle"}, trips_state, start + timedelta(minutes=23))

    assert len(_arrivals(written)) == 1


def test_starting_the_next_trip_is_an_arrival(written):
    trips_state = TripsStateManager()
    start = datetime(2026, 10, 3, 11, 6, tzinfo=EASTERN)
    _heading_to_last_stop(trips_state, start)

    next_trip_at = start + timedelta(minutes=20)
    process_event(
        _update("Route24Bridge-866524-6021", "NEC-2287", 0, "STOPPED_AT", next_trip_at, route_id="CR-Kingston"),
        trips_state,
    )

    [arrival] = [e for e in _arrivals(written) if e["trip_id"] == TRIP]
    assert arrival["event_time"] == next_trip_at


def test_removal_before_the_last_stop_is_not_an_arrival(written):
    trips_state = TripsStateManager()
    start = datetime(2026, 10, 3, 11, 0, tzinfo=EASTERN)
    process_event(_update(TRIP, "MM-0109-S", 60, "STOPPED_AT", start), trips_state)
    process_event(_update(TRIP, "MM-0079-S", 70, "IN_TRANSIT_TO", start + timedelta(minutes=1)), trips_state)

    process_remove({"id": "1823", "type": "vehicle"}, trips_state, start + timedelta(minutes=5))

    assert _arrivals(written) == []


def test_stale_train_is_not_an_arrival(written):
    trips_state = TripsStateManager()
    start = datetime(2026, 10, 3, 11, 6, tzinfo=EASTERN)
    _heading_to_last_stop(trips_state, start)

    process_remove({"id": "1823", "type": "vehicle"}, trips_state, start + timedelta(minutes=45))

    assert _arrivals(written) == []


def test_unknown_vehicle_removal_is_ignored(written):
    process_remove({"id": "9999", "type": "vehicle"}, TripsStateManager(), datetime.now(EASTERN))
    assert written == []
