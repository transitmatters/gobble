from unittest.mock import patch, Mock
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from event import (
    get_stop_name,
    arr_or_dep_event,
    reduce_update_event,
    process_event,
    enrich_event,
    EVENT_TYPE_MAP,
)
from trip_state import TripsStateManager
import gtfs


class TestGetStopName:
    """Test get_stop_name function"""

    def test_get_stop_name_found(self):
        """Test successful stop name lookup"""
        stops_df = pd.DataFrame(
            [
                {"stop_id": "70001", "stop_name": "Harvard Square"},
                {"stop_id": "70002", "stop_name": "Central Square"},
            ]
        )

        result = get_stop_name(stops_df, "70001")
        assert result == "Harvard Square"

    def test_get_stop_name_not_found(self):
        """Test stop name lookup when stop_id doesn't exist"""
        stops_df = pd.DataFrame(
            [
                {"stop_id": "70001", "stop_name": "Harvard Square"},
            ]
        )

        # Should return the stop_id itself when not found
        result = get_stop_name(stops_df, "ER-0117-01")
        assert result == "ER-0117-01"

    def test_get_stop_name_empty_dataframe(self):
        """Test stop name lookup with empty DataFrame"""
        stops_df = pd.DataFrame(columns=["stop_id", "stop_name"])

        result = get_stop_name(stops_df, "70001")
        assert result == "70001"


class TestArrOrDepEvent:
    """Test arr_or_dep_event function for state transitions"""

    def test_departure_event_new_stop(self):
        """Test departure event when moving to a new stop"""
        prev = {"stop_id": "70001", "stop_sequence": 5, "event_type": "ARR"}
        current_status = "IN_TRANSIT_TO"
        current_stop_sequence = 6
        event_type = "DEP"
        stop_id = "70002"

        is_dep, is_arr = arr_or_dep_event(
            prev, current_status, current_stop_sequence, event_type, stop_id
        )

        assert is_dep, "Should be a departure event"
        assert not is_arr, "Should not be an arrival event"

    def test_arrival_event_stopped_after_departure(self):
        """Test arrival event when vehicle stops after being in transit"""
        prev = {"stop_id": "70001", "stop_sequence": 5, "event_type": "DEP"}
        current_status = "STOPPED_AT"
        current_stop_sequence = 6
        event_type = "ARR"
        stop_id = "70002"

        is_dep, is_arr = arr_or_dep_event(
            prev, current_status, current_stop_sequence, event_type, stop_id
        )

        # When moving to a new stop with increased sequence, it's a departure
        assert is_dep, "Should be a departure event (new stop)"
        # STOPPED_AT with prev event_type=DEP creates arrival
        assert is_arr, "Should be an arrival event"

    def test_no_event_same_stop(self):
        """Test no event when still at the same stop"""
        prev = {"stop_id": "70001", "stop_sequence": 5, "event_type": "ARR"}
        current_status = "STOPPED_AT"
        current_stop_sequence = 5
        event_type = "ARR"
        stop_id = "70001"

        is_dep, is_arr = arr_or_dep_event(
            prev, current_status, current_stop_sequence, event_type, stop_id
        )

        assert not is_dep, "Should not be a departure event"
        assert not is_arr, "Should not be an arrival event"

    def test_departure_with_stopped_at_status(self):
        """Test that STOPPED_AT status but at new stop doesn't create arrival if prev was ARR"""
        prev = {"stop_id": "70001", "stop_sequence": 5, "event_type": "ARR"}
        current_status = "STOPPED_AT"
        current_stop_sequence = 6
        event_type = "ARR"
        stop_id = "70002"

        is_dep, is_arr = arr_or_dep_event(
            prev, current_status, current_stop_sequence, event_type, stop_id
        )

        # Different stop with increased sequence = departure
        assert is_dep, "Should be a departure event"
        # STOPPED_AT but prev was ARR not DEP = no arrival
        assert not is_arr, "Should not be an arrival event"


class TestReduceUpdateEvent:
    """Test reduce_update_event function for parsing MBTA API updates"""

    def test_reduce_update_event_basic(self):
        """Test basic event reduction with minimal data"""
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "carriages": [],
                "occupancy_status": "MANY_SEATS_AVAILABLE",
            },
            "relationships": {
                "stop": {"data": {"id": "70001"}},
                "route": {"data": {"id": "Red"}},
                "trip": {"data": {"id": "trip_123"}},
            },
        }

        result = reduce_update_event(update)

        assert result[0] == "IN_TRANSIT_TO"  # current_status
        assert result[1] == "DEP"  # event_type
        assert result[2] == 5  # current_stop_sequence
        assert result[3] == 0  # direction_id
        assert result[4] == "Red"  # route_id
        assert result[5] == "70001"  # stop_id
        assert result[6] == "trip_123"  # trip_id
        assert result[7] == "1234"  # vehicle_label
        assert isinstance(result[8], datetime)  # updated_at
        assert result[9] == "1234"  # vehicle_consist (same as label when no carriages
        assert result[10] == "MANY_SEATS_AVAILABLE"  # occupancy_status
        assert result[11] is None  # occupancy_percentage

    def test_reduce_update_event_with_carriages(self):
        """Test event reduction with multi-carriage consist"""
        update = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 10,
                "direction_id": 1,
                "label": "1234",
                "carriages": [
                    {
                        "label": "0704",
                        "occupancy_status": "MANY_SEATS_AVAILABLE",
                        "occupancy_percentage": 25,
                    },
                    {
                        "label": "0705",
                        "occupancy_status": "FEW_SEATS_AVAILABLE",
                        "occupancy_percentage": 75,
                    },
                ],
            },
            "relationships": {
                "stop": {"data": {"id": "70002"}},
                "route": {"data": {"id": "Orange"}},
                "trip": {"data": {"id": "trip_456"}},
            },
        }

        result = reduce_update_event(update)

        assert result[0] == "STOPPED_AT"
        assert result[1] == "ARR"  # STOPPED_AT maps to ARR
        assert result[9] == "0704|0705"  # vehicle_consist joined with pipe
        assert (
            result[10] == "MANY_SEATS_AVAILABLE|FEW_SEATS_AVAILABLE"
        )  # occupancy_status
        assert result[11] == "25|75"  # occupancy_percentage

    def test_reduce_update_event_carriages_with_null_occupancy(self):
        """Test event reduction when carriages have null occupancy data"""
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 3,
                "direction_id": 0,
                "label": "9999",
                "carriages": [
                    {
                        "label": "0801",
                        "occupancy_status": None,
                        "occupancy_percentage": None,
                    },
                    {
                        "label": "0802",
                        "occupancy_status": None,
                        "occupancy_percentage": None,
                    },
                ],
            },
            "relationships": {
                "stop": {"data": {"id": "70003"}},
                "route": {"data": {"id": "Blue"}},
                "trip": {"data": {"id": "trip_789"}},
            },
        }

        result = reduce_update_event(update)

        assert result[9] == "0801|0802"  # vehicle_consist
        assert result[10] is None  # occupancy_status should be None
        assert result[11] is None  # occupancy_percentage should be None

    def test_reduce_update_event_missing_stop(self):
        """Test event reduction when stop data is missing"""
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 1,
                "direction_id": 0,
                "label": "5678",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": None},  # Missing stop data
                "route": {"data": {"id": "1"}},
                "trip": {"data": {"id": "trip_bus"}},
            },
        }

        result = reduce_update_event(update)

        assert result[5] is None  # stop_id should be None

    def test_reduce_update_event_malformed_stop(self):
        """Test event reduction when stop relationship is completely malformed"""
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 1,
                "direction_id": 1,
                "label": "9999",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": None,  # Completely missing
                "route": {"data": {"id": "28"}},
                "trip": {"data": {"id": "trip_bus2"}},
            },
        }

        result = reduce_update_event(update)

        assert result[5] is None  # stop_id should be None

    def test_reduce_update_event_incoming_at_status(self):
        """Test INCOMING_AT status maps to ARR event type"""
        update = {
            "attributes": {
                "current_status": "INCOMING_AT",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 8,
                "direction_id": 0,
                "label": "1111",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": {"id": "70004"}},
                "route": {"data": {"id": "Green-B"}},
                "trip": {"data": {"id": "trip_green"}},
            },
        }

        result = reduce_update_event(update)

        assert result[0] == "INCOMING_AT"
        assert result[1] == "ARR"  # INCOMING_AT maps to ARR


class TestEnrichEvent:
    """Test enrich_event function"""

    def test_enrich_event(self):
        """Test enrichment of event with GTFS data"""
        # Create a mock GTFS archive
        mock_gtfs_archive = Mock(spec=gtfs.GtfsArchive)

        # Create mock trips and stop_times DataFrames
        mock_trips = pd.DataFrame(
            [
                {
                    "route_id": "Red",
                    "trip_id": "trip_123",
                    "direction_id": 0,
                    "trip_headsign": "Ashmont",
                },
            ]
        )

        mock_stop_times = pd.DataFrame(
            [
                {
                    "trip_id": "trip_123",
                    "stop_id": "70001",
                    "stop_sequence": 5,
                    "arrival_time": pd.Timedelta(hours=10, minutes=30),
                    "departure_time": pd.Timedelta(hours=10, minutes=30),
                },
            ]
        )

        mock_gtfs_archive.trips_by_route_id.return_value = mock_trips
        mock_gtfs_archive.stop_times_by_route_id.return_value = mock_stop_times

        # Create event DataFrame
        event_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=ZoneInfo(key="US/Eastern"))
        df = pd.DataFrame(
            [
                {
                    "service_date": "2024-01-15",
                    "route_id": "Red",
                    "trip_id": "trip_123",
                    "direction_id": 0,
                    "stop_id": "70001",
                    "stop_sequence": 5,
                    "vehicle_id": "0",
                    "vehicle_label": "1234",
                    "event_type": "ARR",
                    "event_time": event_time,
                    "vehicle_consist": "1234",
                    "occupancy_status": None,
                    "occupancy_percentage": None,
                }
            ],
            index=[0],
        )

        # Mock the add_gtfs_headways function
        with patch("gtfs.add_gtfs_headways") as mock_add_headways:
            mock_enriched_df = df.copy()
            mock_enriched_df["scheduled_headway"] = 300.0
            mock_enriched_df["scheduled_trip_id"] = "trip_123"
            mock_enriched_df["scheduled_tt"] = 120
            mock_add_headways.return_value = mock_enriched_df

            result = enrich_event(df, mock_gtfs_archive)

            # Verify the function was called with correct parameters
            mock_gtfs_archive.trips_by_route_id.assert_called_once_with("Red")
            mock_gtfs_archive.stop_times_by_route_id.assert_called_once_with("Red")
            mock_add_headways.assert_called_once()

            # Verify result is a dict
            assert isinstance(result, dict)
            assert result["route_id"] == "Red"
            assert result["scheduled_headway"] == 300.0


class TestProcessEvent:
    """Test process_event function - the main event processing pipeline"""

    def setup_method(self):
        """Set up common test fixtures"""
        self.mock_trips_state = Mock(spec=TripsStateManager)
        self.mock_trips_state.get_trip_state.return_value = None

    @patch("event.gtfs.get_current_gtfs_archive")
    @patch("event.disk.write_event")
    def test_process_event_first_departure(self, mock_write_event, mock_get_gtfs):
        """Test processing first departure event for a trip"""
        # Mock GTFS archive
        mock_gtfs_archive = Mock(spec=gtfs.GtfsArchive)
        mock_stops_df = pd.DataFrame(
            [
                {"stop_id": "70001", "stop_name": "Harvard Square"},
                {"stop_id": "70002", "stop_name": "Central Square"},
            ]
        )
        mock_gtfs_archive.stops = mock_stops_df
        mock_gtfs_archive.trips_by_route_id.return_value = pd.DataFrame()
        mock_gtfs_archive.stop_times_by_route_id.return_value = pd.DataFrame()
        mock_get_gtfs.return_value = mock_gtfs_archive

        # Create update event
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 2,
                "direction_id": 0,
                "label": "1234",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": {"id": "70002"}},
                "route": {"data": {"id": "Red"}},
                "trip": {"data": {"id": "trip_123"}},
            },
        }

        # Mock initial trip state
        self.mock_trips_state.get_trip_state.return_value = {
            "stop_sequence": 1,
            "stop_id": "70001",
            "updated_at": "2024-01-15T10:25:00-05:00",
            "event_type": "ARR",
        }

        with patch("event.enrich_event") as mock_enrich:
            mock_enrich.return_value = {"route_id": "Red", "event_type": "DEP"}

            process_event(update, self.mock_trips_state)

            # Verify GTFS archive was fetched
            mock_get_gtfs.assert_called_once()

            # Verify enrich_event was called
            mock_enrich.assert_called_once()

            # Verify event was written to disk
            mock_write_event.assert_called_once()

            # Verify trip state was updated
            self.mock_trips_state.set_trip_state.assert_called_once()
            call_args = self.mock_trips_state.set_trip_state.call_args
            assert call_args[0][0] == "Red"  # route_id
            assert call_args[0][1] == "trip_123"  # trip_id
            assert call_args[0][2]["stop_sequence"] == 2
            # Note: Due to line 144 in event.py, stop_id gets reassigned to prev stop for departures
            # This affects both the event written AND the trip state update
            assert call_args[0][2]["stop_id"] == "70001"

    @patch("event.gtfs.get_current_gtfs_archive")
    @patch("event.disk.write_event")
    def test_process_event_skips_event_with_no_stop(
        self, mock_write_event, mock_get_gtfs
    ):
        """Test that events with no stop_id are skipped"""
        update = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 1,
                "direction_id": 0,
                "label": "1234",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": None},  # Missing stop
                "route": {"data": {"id": "Red"}},
                "trip": {"data": {"id": "trip_123"}},
            },
        }

        process_event(update, self.mock_trips_state)

        # Should skip processing and not write event
        mock_write_event.assert_not_called()
        mock_get_gtfs.assert_not_called()

    @patch("event.gtfs.get_current_gtfs_archive")
    @patch("event.disk.write_event")
    def test_process_event_filters_bus_stops(
        self, mock_write_event, mock_get_gtfs
    ):
        """Test that only configured bus stops are written"""

        mock_gtfs_archive = Mock(spec=gtfs.GtfsArchive)
        # Include both stops in the GTFS data
        mock_stops_df = pd.DataFrame(
            [
                {"stop_id": "10000", "stop_name": "Bus Stop 0"},
                {"stop_id": "10001", "stop_name": "Bus Stop 1"},
            ]
        )
        mock_gtfs_archive.stops = mock_stops_df
        mock_gtfs_archive.trips_by_route_id.return_value = pd.DataFrame()
        mock_gtfs_archive.stop_times_by_route_id.return_value = pd.DataFrame()
        mock_get_gtfs.return_value = mock_gtfs_archive

        # Patch BUS_STOPS with test data using monkeypatch
        import constants

        with patch.dict(constants.BUS_STOPS, {"1": {"10000", "10001"}}, clear=False):
            # Update showing vehicle in transit to stop 10001 (creates departure from 10000)
            update_at_configured_stop = {
                "attributes": {
                    "current_status": "IN_TRANSIT_TO",
                    "updated_at": "2024-01-15T10:30:00-05:00",
                    "current_stop_sequence": 2,
                    "direction_id": 0,
                    "label": "bus123",
                    "carriages": [],
                    "occupancy_status": None,
                },
                "relationships": {
                    "stop": {"data": {"id": "10001"}},  # Next stop
                    "route": {"data": {"id": "1"}},
                    "trip": {"data": {"id": "bus_trip_123"}},
                },
            }

            # Previous state at stop 10000 (this will be the departure stop)
            self.mock_trips_state.get_trip_state.return_value = {
                "stop_sequence": 1,
                "stop_id": "10000",
                "updated_at": "2024-01-15T10:25:00-05:00",
                "event_type": "ARR",
            }

            with patch("event.enrich_event") as mock_enrich:
                mock_enrich.return_value = {"route_id": "1", "event_type": "DEP"}

                process_event(update_at_configured_stop, self.mock_trips_state)

                # Should write event for configured bus stop (departure from 10000)
                mock_write_event.assert_called_once()

    @patch("event.gtfs.get_current_gtfs_archive")
    @patch("event.disk.write_event")
    def test_process_event_no_write_for_non_event(
        self, mock_write_event, mock_get_gtfs
    ):
        """Test that no event is written when neither departure nor arrival occurs"""
        update = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": {"id": "70001"}},
                "route": {"data": {"id": "Red"}},
                "trip": {"data": {"id": "trip_123"}},
            },
        }

        # Same stop, same sequence - no departure or arrival
        self.mock_trips_state.get_trip_state.return_value = {
            "stop_sequence": 5,
            "stop_id": "70001",
            "updated_at": "2024-01-15T10:25:00-05:00",
            "event_type": "ARR",
        }

        process_event(update, self.mock_trips_state)

        # No event should be written
        mock_write_event.assert_not_called()

        # But trip state should still be updated
        self.mock_trips_state.set_trip_state.assert_called_once()

    @patch("event.gtfs.get_current_gtfs_archive")
    @patch("event.disk.write_event")
    def test_process_event_first_time_seeing_trip(
        self, mock_write_event, mock_get_gtfs
    ):
        """Test processing event when trip has no previous state (line 123)"""
        # Mock GTFS archive
        mock_gtfs_archive = Mock(spec=gtfs.GtfsArchive)
        mock_stops_df = pd.DataFrame(
            [
                {"stop_id": "70001", "stop_name": "Harvard Square"},
                {"stop_id": "70002", "stop_name": "Central Square"},
            ]
        )
        mock_gtfs_archive.stops = mock_stops_df
        mock_gtfs_archive.trips_by_route_id.return_value = pd.DataFrame()
        mock_gtfs_archive.stop_times_by_route_id.return_value = pd.DataFrame()
        mock_get_gtfs.return_value = mock_gtfs_archive

        # Create update event
        update = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2024-01-15T10:30:00-05:00",
                "current_stop_sequence": 1,
                "direction_id": 0,
                "label": "1234",
                "carriages": [],
                "occupancy_status": None,
            },
            "relationships": {
                "stop": {"data": {"id": "70001"}},
                "route": {"data": {"id": "Red"}},
                "trip": {"data": {"id": "trip_new"}},
            },
        }

        # Return None to simulate first time seeing this trip
        self.mock_trips_state.get_trip_state.return_value = None

        with patch("event.enrich_event") as mock_enrich:
            mock_enrich.return_value = {"route_id": "Red", "event_type": "ARR"}

            process_event(update, self.mock_trips_state)

            # Verify trip state was initialized and set
            self.mock_trips_state.set_trip_state.assert_called_once()
            call_args = self.mock_trips_state.set_trip_state.call_args
            assert call_args[0][0] == "Red"  # route_id
            assert call_args[0][1] == "trip_new"  # trip_id
            # Check that the prev_trip_state was initialized with current values
            assert call_args[0][2]["stop_sequence"] == 1
            assert call_args[0][2]["stop_id"] == "70001"
            assert call_args[0][2]["event_type"] == "ARR"


class TestEventTypeMap:
    """Test EVENT_TYPE_MAP constant"""

    def test_event_type_map_has_expected_mappings(self):
        """Verify the event type mappings are correct"""
        assert EVENT_TYPE_MAP["IN_TRANSIT_TO"] == "DEP"
        assert EVENT_TYPE_MAP["STOPPED_AT"] == "ARR"
        assert EVENT_TYPE_MAP["INCOMING_AT"] == "ARR"
        assert len(EVENT_TYPE_MAP) == 3
