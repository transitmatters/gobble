import datetime
import numpy as np
import pandas as pd
import pathlib
import shutil
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pytest
from util import to_dateint

import gtfs

DATA_DIR = pathlib.Path("./src/tests/sample_data")


@pytest.fixture(scope="class")
def gtfs_test_data():
    """Load GTFS test data once per test class."""
    stop_times = pd.read_csv(
        DATA_DIR / "stops_times_mini.txt",
        dtype={"trip_id": str, "stop_id": str},
        usecols=gtfs.STOP_TIMES_COLS,
    )
    stop_times.arrival_time = pd.to_timedelta(stop_times.arrival_time)
    stop_times.departure_time = pd.to_timedelta(stop_times.departure_time)

    all_trips = pd.read_csv(
        DATA_DIR / "trips_mini.txt", dtype={"trip_short_name": str, "block_id": str}
    )

    return {"stop_times": stop_times, "all_trips": all_trips}


def _format_expected_headway_df(expected: dict) -> pd.DataFrame:
    """Helper to format expected df because types are awful"""
    expected_df = pd.DataFrame([expected], index=[0])
    expected_df["arrival_time"] = expected_df["event_time"] - datetime.datetime(
        2024, 1, 4, tzinfo=ZoneInfo(key="US/Eastern")
    )
    expected_df["scheduled_tt"] = expected_df["scheduled_tt"].astype("int32")
    return expected_df


class TestGTFS:
    @pytest.fixture(autouse=True)
    def setup(self, gtfs_test_data):
        """Setup test data for all test methods."""
        self.stop_times = gtfs_test_data["stop_times"]
        self.all_trips = gtfs_test_data["all_trips"]

    def test_add_gtfs_headways_batch(self):
        # expected stop info....
        # 60063977,05:10:00,05:10:00,10003,5,,0,0,0,,,
        # on time, slightly late
        on_time = datetime.datetime(
            2024, 1, 4, 5, 11, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
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
        little_early = datetime.datetime(
            2024, 1, 4, 5, 9, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
        event["event_time"] = little_early
        expected["event_time"] = little_early
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # very late: so late that we use the next stop for headway calcs
        very_late = datetime.datetime(
            2024, 1, 4, 5, 26, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
        event["event_time"] = very_late
        expected["event_time"] = very_late
        expected["scheduled_trip_id"] = "60063980"
        expected["trip_id_gtfs"] = "60063980"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.batch_add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # so early youve made the prior bus
        very_early = datetime.datetime(
            2024, 1, 4, 4, 45, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
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
        on_time = datetime.datetime(
            2024, 1, 4, 5, 11, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
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
        little_early = datetime.datetime(
            2024, 1, 4, 5, 9, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
        event["event_time"] = little_early
        expected["event_time"] = little_early
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # very late: so late that we use the next stop for headway calcs
        very_late = datetime.datetime(
            2024, 1, 4, 5, 26, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
        event["event_time"] = very_late
        expected["event_time"] = very_late
        expected["scheduled_trip_id"] = "60063980"
        expected["trip_id_gtfs"] = "60063980"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

        # so early youve made the prior bus
        very_early = datetime.datetime(
            2024, 1, 4, 4, 45, 45, 188670, tzinfo=ZoneInfo(key="US/Eastern")
        )
        event["event_time"] = very_early
        expected["event_time"] = very_early
        expected["scheduled_headway"] = np.nan
        expected["scheduled_trip_id"] = "60063972"
        expected["trip_id_gtfs"] = "60063972"
        df = pd.DataFrame([event], index=[0])
        expected_df = _format_expected_headway_df(expected)

        post_df = gtfs.add_gtfs_headways(df, self.all_trips, self.stop_times)
        pd.testing.assert_frame_equal(post_df, expected_df)

    @pytest.mark.integration
    @patch('gtfs.urllib.request.urlretrieve')
    @patch('gtfs._download_gtfs_archives_list')
    @patch('gtfs.shutil.unpack_archive')
    def test_get_gtfs_archive_day_is_feed_returns_dir_of_day(
        self, mock_unpack, mock_download_list, mock_urlretrieve
    ):
        # just a random day
        day_to_test: int = 20240807
        expected_path: str = f"data/gtfs_archives/{day_to_test}"

        # Mock the archives list to return data for this date
        mock_archives_df = pd.DataFrame({
            'feed_start_date': [20240807],
            'feed_end_date': [20240813],
            'archive_url': [f'https://example.com/{day_to_test}.zip']
        })
        mock_download_list.return_value = mock_archives_df

        # Mock urlretrieve to return a fake zipfile path
        mock_urlretrieve.return_value = ('/tmp/fake.zip', None)

        # Create the expected directory so pathlib.Path.exists() returns True
        pathlib.Path(expected_path).mkdir(parents=True, exist_ok=True)

        result = gtfs.get_gtfs_archive(day_to_test)

        assert str(result) == expected_path
        assert pathlib.Path.exists(result)

        # cleanup
        shutil.rmtree(expected_path)

    @pytest.mark.integration
    @patch('gtfs.urllib.request.urlretrieve')
    @patch('gtfs._download_gtfs_archives_list')
    @patch('gtfs.shutil.unpack_archive')
    def test_get_gtfs_archive_day_not_feed_returns_dir_of_feed_containing_day(
        self, mock_unpack, mock_download_list, mock_urlretrieve
    ):
        # from https://cdn.mbta.com/archive/archived_feeds.txt
        # 20240802,20240806,"Summer 2024, 2024-08-09T21:10:59+00:00, version D",https://cdn.mbtace.com/archive/20240802.zip,fix: Correct wrong-direction stop sequences etc in existing Ashmont-Mattapan shuttle definition; Add shuttle activation for 08/16-18 Mattapan shuttle; Replace Mattapan Line service during 08/16-18 suspension for track work; Add missing 25:00 info to shuttle activation; Fix formatting; Whoops! Change
        day_to_test: int = 20240804
        expected_path: str = "data/gtfs_archives/20240802"

        # Mock the archives list to return a feed that spans the test date
        mock_archives_df = pd.DataFrame({
            'feed_start_date': [20240802],
            'feed_end_date': [20240806],
            'archive_url': ['https://example.com/20240802.zip']
        })
        mock_download_list.return_value = mock_archives_df

        # Mock urlretrieve to return a fake zipfile path
        mock_urlretrieve.return_value = ('/tmp/fake.zip', None)

        # Create the expected directory so pathlib.Path.exists() returns True
        pathlib.Path(expected_path).mkdir(parents=True, exist_ok=True)

        result = gtfs.get_gtfs_archive(day_to_test)

        assert str(result) == expected_path
        assert pathlib.Path.exists(result)

        # cleanup
        shutil.rmtree(expected_path)

    @pytest.mark.integration
    def test_read_gtfs_date_exists_feed_is_read(self):
        # This test uses MBTA-specific route IDs and destinations
        day_to_test = datetime.date(2024, 8, 7)
        expected_path: str = f"data/gtfs_archives/{to_dateint(day_to_test)}"

        result = gtfs.read_gtfs(day_to_test)

        assert result.service_date == day_to_test

        orange_line_trips = result.trips_by_route_id("Orange")
        assert not orange_line_trips.empty

        # sanity check we have trips for each termini of the orange line
        assert "Forest Hills" in orange_line_trips["trip_headsign"].values
        assert "Oak Grove" in orange_line_trips["trip_headsign"].values

        # sanity check stops exist for the red line
        assert not result.stop_times_by_route_id("Red").empty
        # red line has stop data for ashmont
        assert "70094" in result.stop_times_by_route_id("Red")["stop_id"].values

        # the 1 bus has trips to harcard
        assert not result.trips_by_route_id("1").empty
        assert "Harvard" in result.trips_by_route_id("1")["trip_headsign"].values

        shutil.rmtree(expected_path)
