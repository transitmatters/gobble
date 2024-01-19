import unittest
import datetime
import numpy as np
import pandas as pd
import pathlib
from zoneinfo import ZoneInfo

import gtfs

DATA_DIR = pathlib.Path("./src/tests/sample_data")


def _format_expected_headway_df(expected: dict) -> pd.DataFrame:
    """Helper to format expected df because types are awful"""
    expected_df = pd.DataFrame([expected], index=[0])
    expected_df["arrival_time"] = expected_df["event_time"] - datetime.datetime(
        2024, 1, 4, tzinfo=ZoneInfo(key="US/Eastern")
    )
    expected_df["scheduled_tt"] = expected_df["scheduled_tt"].astype("int32")
    return expected_df


class TestGTFS(unittest.TestCase):
    def setUp(self):
        # load stop times and trips
        self.stop_times = pd.read_csv(
            DATA_DIR / "stops_times_mini.txt", dtype={"trip_id": str, "stop_id": str}, usecols=gtfs.STOP_TIMES_COLS
        )
        self.stop_times.arrival_time = pd.to_timedelta(self.stop_times.arrival_time)
        self.stop_times.departure_time = pd.to_timedelta(self.stop_times.departure_time)

        self.all_trips = pd.read_csv(DATA_DIR / "trips_mini.txt", dtype={"trip_short_name": str, "block_id": str})

    def test_add_gtfs_headways_batch(self):
        # expected stop info....
        # 60063977,05:10:00,05:10:00,10003,5,,0,0,0,,,
        # on time, slightly late
        on_time = datetime.datetime(2024, 1, 4, 5, 11, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event = {
            "service_date": datetime.date(2024, 1, 4),
            "route_id": "1",
            "trip_id": "60063977",
            "direction_id": 0,
            "stop_id": "10003",
            "stop_sequence": 5,
            "vehicle_id": "0",  # TODO??
            "vehicle_label": "catbus",
            "event_type": "ARR",
            "event_time": on_time,
        }

        expected = {
            "service_date": datetime.date(2024, 1, 4),
            "route_id": "1",
            "trip_id": "60063977",
            "direction_id": 0,
            "stop_id": "10003",
            "stop_sequence": 5,
            "vehicle_id": "0",
            "vehicle_label": "catbus",
            "event_type": "ARR",
            "event_time": on_time,
            "arrival_time": None,
            "scheduled_headway": 900.0,
            "scheduled_trip_id": "60063977",
            "trip_id_gtfs": "60063977",
            "scheduled_tt": 180,
        }

        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # little early
        little_early = datetime.datetime(2024, 1, 4, 5, 9, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = little_early
        expected["event_time"] = little_early
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # very late: so late that we use the next stop for headway calcs
        very_late = datetime.datetime(2024, 1, 4, 5, 26, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = very_late
        expected["event_time"] = very_late
        expected["scheduled_trip_id"] = "60063980"
        expected["trip_id_gtfs"] = "60063980"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # so early youve made the prior bus
        very_early = datetime.datetime(2024, 1, 4, 4, 45, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = very_early
        expected["event_time"] = very_early
        expected["scheduled_headway"] = np.nan
        expected["scheduled_trip_id"] = "60063972"
        expected["trip_id_gtfs"] = "60063972"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

    def test_add_gtfs_headways(self):
        # expected stop info....
        # 60063977,05:10:00,05:10:00,10003,5,,0,0,0,,,
        # on time, slightly late
        on_time = datetime.datetime(2024, 1, 4, 5, 11, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event = {
            "service_date": datetime.date(2024, 1, 4),
            "route_id": "1",
            "trip_id": "60063977",
            "direction_id": 0,
            "stop_id": "10003",
            "stop_sequence": 5,
            "vehicle_id": "0",  # TODO??
            "vehicle_label": "catbus",
            "event_type": "ARR",
            "event_time": on_time,
        }

        expected = {
            "service_date": datetime.date(2024, 1, 4),
            "route_id": "1",
            "trip_id": "60063977",
            "direction_id": 0,
            "stop_id": "10003",
            "stop_sequence": 5,
            "vehicle_id": "0",
            "vehicle_label": "catbus",
            "event_type": "ARR",
            "event_time": on_time,
            "arrival_time": None,
            "scheduled_headway": 900.0,
            "scheduled_trip_id": "60063977",
            "trip_id_gtfs": "60063977",
            "scheduled_tt": 180,
        }

        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # little early
        little_early = datetime.datetime(2024, 1, 4, 5, 9, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = little_early
        expected["event_time"] = little_early
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # very late: so late that we use the next stop for headway calcs
        very_late = datetime.datetime(2024, 1, 4, 5, 26, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = very_late
        expected["event_time"] = very_late
        expected["scheduled_trip_id"] = "60063980"
        expected["trip_id_gtfs"] = "60063980"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # so early youve made the prior bus
        very_early = datetime.datetime(2024, 1, 4, 4, 45, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern"))
        event["event_time"] = very_early
        expected["event_time"] = very_early
        expected["scheduled_headway"] = np.nan
        expected["scheduled_trip_id"] = "60063972"
        expected["trip_id_gtfs"] = "60063972"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)
