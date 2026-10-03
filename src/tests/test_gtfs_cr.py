import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import gtfs

EASTERN = ZoneInfo("US/Eastern")
SERVICE_DATE = datetime.date(2026, 10, 1)

LOCAL = "Base-1-500"
EXPRESS = "Base-2-502"

STOPS = pd.DataFrame(
    [
        {"stop_id": "WML-0214-02", "parent_station": "place-WML-0214"},
        {"stop_id": "WML-0147-02", "parent_station": "place-WML-0147"},
        {"stop_id": "WML-0012-05", "parent_station": "place-bbsta"},
        {"stop_id": "WML-0012-07", "parent_station": "place-bbsta"},
        {"stop_id": "NEC-2287", "parent_station": "place-sstat"},
        {"stop_id": "NEC-2287-03", "parent_station": "place-sstat"},
        {"stop_id": "no-parent", "parent_station": np.nan},
    ]
)
STATIONS = dict(zip(STOPS.stop_id, STOPS.parent_station.fillna(STOPS.stop_id)))

TRIPS = pd.DataFrame(
    [
        {"route_id": "CR-Worcester", "trip_id": LOCAL, "trip_short_name": "500", "direction_id": 1},
        {"route_id": "CR-Worcester", "trip_id": EXPRESS, "trip_short_name": "502", "direction_id": 1},
    ]
)


def _stop_time(trip_id, stop_id, sequence, hhmm):
    time = pd.Timedelta(f"{hhmm}:00")
    return {
        "trip_id": trip_id,
        "stop_id": stop_id,
        "stop_sequence": sequence,
        "arrival_time": time,
        "departure_time": time,
    }


# The schedule lists platform tracks along the line but only the station at South Station
STOP_TIMES = pd.DataFrame(
    [
        _stop_time(LOCAL, "WML-0214-02", 1, "07:00"),
        _stop_time(LOCAL, "WML-0147-02", 2, "07:15"),
        _stop_time(LOCAL, "WML-0012-05", 3, "07:40"),
        _stop_time(LOCAL, "NEC-2287", 4, "07:47"),
        _stop_time(EXPRESS, "WML-0214-02", 1, "07:05"),
        _stop_time(EXPRESS, "WML-0012-05", 3, "07:30"),
        _stop_time(EXPRESS, "NEC-2287", 4, "07:37"),
    ]
)


def _event(trip_id, stop_id, hour, minute):
    return pd.DataFrame(
        [
            {
                "service_date": SERVICE_DATE,
                "route_id": "CR-Worcester",
                "trip_id": trip_id,
                "direction_id": 1,
                "stop_id": stop_id,
                "stop_sequence": 3,
                "event_type": "ARR",
                "event_time": datetime.datetime(2026, 10, 1, hour, minute, tzinfo=EASTERN),
            }
        ],
        index=[0],
    )


def _scheduled(event_df):
    return gtfs.add_cr_scheduled_values(event_df, TRIPS, STOP_TIMES, STATIONS).iloc[0]


def test_late_express_keeps_its_own_schedule():
    # Six minutes late into Back Bay, the express is nearer the local's 7:40 than its own 7:30.
    # It must still be benchmarked against the express schedule, on a different track than scheduled.
    result = _scheduled(_event(EXPRESS, "WML-0012-07", 7, 36))
    assert result.scheduled_trip_id == EXPRESS
    assert result.scheduled_tt == 25 * 60


def test_terminal_track_matches_scheduled_station():
    result = _scheduled(_event(EXPRESS, "NEC-2287-03", 7, 40))
    assert result.scheduled_tt == 32 * 60


def test_scheduled_headway_is_the_gap_to_the_previous_train_at_the_station():
    assert _scheduled(_event(LOCAL, "WML-0012-05", 7, 41)).scheduled_headway == 10 * 60
    assert np.isnan(_scheduled(_event(EXPRESS, "WML-0012-05", 7, 31)).scheduled_headway)


def test_unscheduled_stop_has_no_benchmark():
    # The express doesn't stop at Wellesley Square
    result = _scheduled(_event(EXPRESS, "WML-0147-02", 7, 16))
    assert result.scheduled_trip_id == EXPRESS
    assert np.isnan(result.scheduled_tt)


def test_falls_back_to_train_number():
    assert gtfs.match_scheduled_cr_trip("Renamed-999-502", TRIPS) == EXPRESS
    assert gtfs.match_scheduled_cr_trip("ADDED-1", TRIPS) is None


def test_unknown_trip_falls_back_to_time_matching():
    result = _scheduled(_event("ADDED-1", "WML-0012-05", 7, 39))
    assert result.scheduled_trip_id == LOCAL


@pytest.mark.parametrize("stop_id, station", [("NEC-2287-03", "place-sstat"), ("no-parent", "no-parent")])
def test_archive_maps_stops_to_stations(stop_id, station):
    archive = gtfs.GtfsArchive(trips=TRIPS, stop_times=STOP_TIMES, stops=STOPS, service_date=SERVICE_DATE)
    assert archive.station_by_stop_id()[stop_id] == station
