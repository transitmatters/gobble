import unittest
from unittest.mock import patch
from datetime import datetime, date, timedelta
from pathlib import Path
from trip_state import RouteTripsState
from util import EASTERN_TIME


class TestTripStatePerformance(unittest.TestCase):

    def test_get_trip_state_does_not_call_expensive_operations(self):
        """get_trip_state should be fast and not do cleanup or file writes"""
        state = RouteTripsState("1")

        # Add a trip
        trip_state = {
            "stop_sequence": 5,
            "stop_id": "123",
            "updated_at": datetime.now(EASTERN_TIME),
            "event_type": "ARR",
            "vehicle_consist": "0704|0705|0790|0791|0749|0748",
        }
        state.trips["trip_123"] = trip_state

        # Mock expensive operations to ensure they're not called
        with (
            patch.object(state, "_cleanup_trip_states") as mock_cleanup,
            patch("trip_state.write_trips_state_file") as mock_write,
        ):

            # Call get_trip_state multiple times
            result1 = state.get_trip_state("trip_123")
            result2 = state.get_trip_state("trip_456")  # Non-existent
            result3 = state.get_trip_state("trip_123")

            # Verify expensive operations were NOT called
            mock_cleanup.assert_not_called()
            mock_write.assert_not_called()

            # Verify correct results
            self.assertEqual(result1["stop_sequence"], 5)
            self.assertIsNone(result2)
            self.assertEqual(result3["stop_sequence"], 5)


class TestTripStateCleanup(unittest.TestCase):

    def test_cleanup_removes_stale_trips(self):
        """Cleanup should remove trips older than 5 hours"""
        state = RouteTripsState("1")
        current_time = datetime.now(EASTERN_TIME)

        # Add fresh trip (should be kept)
        fresh_trip = {
            "stop_sequence": 1,
            "stop_id": "123",
            "updated_at": current_time - timedelta(hours=1),
            "event_type": "ARR",
        }

        # Add stale trip (should be removed)
        stale_trip = {
            "stop_sequence": 2,
            "stop_id": "456",
            "updated_at": current_time - timedelta(hours=6),
            "event_type": "DEP",
        }

        state.trips["fresh_trip"] = fresh_trip
        state.trips["stale_trip"] = stale_trip

        # Run cleanup
        state._cleanup_stale_trip_states()

        # Verify stale trip removed, fresh trip kept
        self.assertIn("fresh_trip", state.trips)
        self.assertNotIn("stale_trip", state.trips)

    def test_overnight_purge_clears_all_trips(self):
        """Service date change should clear all trips"""
        state = RouteTripsState("1")
        state.service_date = date(2024, 1, 1)  # Old date

        # Add some trips
        state.trips["trip1"] = {
            "stop_sequence": 1,
            "stop_id": "123",
            "updated_at": datetime.now(EASTERN_TIME),
            "event_type": "ARR",
        }
        state.trips["trip2"] = {
            "stop_sequence": 2,
            "stop_id": "456",
            "updated_at": datetime.now(EASTERN_TIME),
            "event_type": "DEP",
        }

        with patch("trip_state.get_current_service_date", return_value=date(2024, 1, 2)):
            state._purge_trips_state_if_overnight()

        # All trips should be cleared
        self.assertEqual(len(state.trips), 0)
        self.assertEqual(state.service_date, date(2024, 1, 2))


class TestTripStateFileIO(unittest.TestCase):

    @patch("trip_state.write_trips_state_file")
    def test_set_trip_state_writes_once(self, mock_write):
        """set_trip_state should write to file exactly once after all cleanup"""
        state = RouteTripsState("1")

        trip_state = {
            "stop_sequence": 5,
            "stop_id": "123",
            "updated_at": datetime.now(EASTERN_TIME),
            "event_type": "ARR",
            "vehicle_consist": "0704|0705|0790|0791|0749|0748",
        }

        state.set_trip_state("trip_123", trip_state)

        # Should write exactly once
        mock_write.assert_called_once_with("1", state)


class TestTripStateIntegration(unittest.TestCase):

    @patch("trip_state.write_trips_state_file")
    @patch("trip_state.read_trips_state_file", return_value=None)
    def test_realistic_workflow(self, mock_read, mock_write):
        """Test a realistic sequence of operations"""
        state = RouteTripsState("1")
        current_time = datetime.now(EASTERN_TIME)

        # Add several trips over time
        for i in range(10):
            trip_state = {
                "stop_sequence": i,
                "stop_id": f"stop_{i}",
                "updated_at": current_time - timedelta(hours=i),
                "event_type": "ARR" if i % 2 == 0 else "DEP",
            }
            state.set_trip_state(f"trip_{i}", trip_state)

        # Verify recent trips are accessible
        recent_trip = state.get_trip_state("trip_0")  # 0 hours old
        self.assertIsNotNone(recent_trip)

        old_trip = state.get_trip_state("trip_8")  # 8 hours old - should be cleaned up
        self.assertIsNone(old_trip)

        # Verify we kept reasonable number of trips
        self.assertTrue(len(state.trips) < 10)  # Some should be cleaned up
        self.assertTrue(len(state.trips) > 0)  # But not all


class TestTripStateFilePersistence(unittest.TestCase):

    def setUp(self):
        """Set up temporary file location for testing"""
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = None

    def tearDown(self):
        """Clean up temporary files"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_updated_after_cleanup(self):
        """Test that file is written after cleanup removes stale trips"""
        # Patch DATA_DIR directly in the trip_state module
        temp_data_dir = Path(self.temp_dir)

        with patch("trip_state.DATA_DIR", temp_data_dir):
            state = RouteTripsState("test_route")
            current_time = datetime.now(EASTERN_TIME)

            # Add fresh trip and stale trip
            fresh_trip = {
                "stop_sequence": 1,
                "stop_id": "fresh_stop",
                "updated_at": current_time - timedelta(hours=1),
                "event_type": "ARR",
            }

            stale_trip = {
                "stop_sequence": 2,
                "stop_id": "stale_stop",
                "updated_at": current_time - timedelta(hours=6),  # Older than 5 hours
                "event_type": "DEP",
            }

            # Add trips directly to avoid triggering cleanup
            state.trips["fresh_trip"] = fresh_trip
            state.trips["stale_trip"] = stale_trip

            # Trigger cleanup by setting a new trip
            new_trip = {
                "stop_sequence": 3,
                "stop_id": "new_stop",
                "updated_at": current_time,
                "event_type": "ARR",
            }
            state.set_trip_state("new_trip", new_trip)

            # Verify file exists and can be read
            trip_file_path = temp_data_dir / "trip_states" / "test_route.json"
            self.assertTrue(trip_file_path.exists(), "Trip state file should exist after cleanup")

            # Read the file and verify contents
            import json

            with open(trip_file_path, "r") as f:
                file_contents = json.load(f)

            # Should contain service date and trip states
            self.assertIn("service_date", file_contents)
            self.assertIn("trip_states", file_contents)

            # Should have fresh and new trip, but not stale trip
            trip_states = file_contents["trip_states"]
            self.assertIn("fresh_trip", trip_states)
            self.assertIn("new_trip", trip_states)
            self.assertNotIn("stale_trip", trip_states, "Stale trip should have been cleaned up")

    def test_file_updated_after_overnight_purge(self):
        """Test that file is written after overnight purge clears all trips"""
        temp_data_dir = Path(self.temp_dir)

        with patch("trip_state.DATA_DIR", temp_data_dir):
            state = RouteTripsState("test_route")
            state.service_date = date(2024, 1, 1)  # Old service date

            # Add some trips
            current_time = datetime.now(EASTERN_TIME)
            for i in range(3):
                trip_state = {
                    "stop_sequence": i,
                    "stop_id": f"stop_{i}",
                    "updated_at": current_time,
                    "event_type": "ARR",
                }
                state.trips[f"trip_{i}"] = trip_state

            # Mock service date to trigger purge
            with patch("trip_state.get_current_service_date", return_value=date(2024, 1, 2)):
                # Trigger purge by setting a new trip
                new_trip = {
                    "stop_sequence": 10,
                    "stop_id": "new_stop",
                    "updated_at": current_time,
                    "event_type": "DEP",
                }
                state.set_trip_state("new_trip", new_trip)

            # Verify file exists and can be read
            trip_file_path = temp_data_dir / "trip_states" / "test_route.json"
            self.assertTrue(trip_file_path.exists(), "Trip state file should exist after purge")

            # Read file and verify contents
            import json

            with open(trip_file_path, "r") as f:
                file_contents = json.load(f)

            # Should have updated service date
            self.assertEqual(file_contents["service_date"], "2024-01-02")

            # Should only have the new trip (old ones purged)
            trip_states = file_contents["trip_states"]
            self.assertEqual(len(trip_states), 1)
            self.assertIn("new_trip", trip_states)
            self.assertNotIn("trip_0", trip_states)
            self.assertNotIn("trip_1", trip_states)
            self.assertNotIn("trip_2", trip_states)

    def test_file_can_be_read_back_correctly(self):
        """Test that data written to file can be read back and creates correct state"""
        temp_data_dir = Path(self.temp_dir)

        with patch("trip_state.DATA_DIR", temp_data_dir):
            # Create first state and add some trips
            state1 = RouteTripsState("test_route")
            current_time = datetime.now(EASTERN_TIME)

            original_trips = {}
            for i in range(3):
                trip_state = {
                    "stop_sequence": i + 1,
                    "stop_id": f"stop_{i}",
                    "updated_at": current_time - timedelta(hours=i),
                    "event_type": "ARR" if i % 2 == 0 else "DEP",
                }
                state1.set_trip_state(f"trip_{i}", trip_state)
                original_trips[f"trip_{i}"] = trip_state

            # Create new state for same route - should read from file
            state2 = RouteTripsState("test_route")

            # Verify the trips were loaded correctly
            self.assertEqual(len(state2.trips), len(original_trips))

            for trip_id, original_trip in original_trips.items():
                loaded_trip = state2.get_trip_state(trip_id)
                self.assertIsNotNone(loaded_trip, f"Trip {trip_id} should be loaded from file")
                self.assertEqual(loaded_trip["stop_sequence"], original_trip["stop_sequence"])
                self.assertEqual(loaded_trip["stop_id"], original_trip["stop_id"])
                self.assertEqual(loaded_trip["event_type"], original_trip["event_type"])
                # Note: updated_at will be datetime object after loading
