import csv
import datetime
import pathlib
import pytest

import disk
from util import EASTERN_TIME


@pytest.fixture
def temp_disk_dir(tmp_path, monkeypatch):
    """Fixture providing temporary directory for disk tests"""
    original_data_dir = disk.DATA_DIR
    monkeypatch.setattr(disk, "DATA_DIR", tmp_path)
    yield tmp_path
    disk.DATA_DIR = original_data_dir


class TestWriteEvent:
    """Test write_event function"""

    def test_write_event_creates_new_file_with_header(self, temp_disk_dir):
        """Test writing first event creates file with CSV header"""
        event = {
            "service_date": "2024-01-15",
            "route_id": "Red",
            "trip_id": "trip_123",
            "direction_id": 0,
            "stop_id": "70001",
            "stop_sequence": 5,
            "vehicle_id": "0",
            "vehicle_label": "1234",
            "event_type": "ARR",
            "event_time": datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 300.0,
            "scheduled_tt": 120,
            "vehicle_consist": "1234",
            "occupancy_status": None,
            "occupancy_percentage": None,
        }

        disk.write_event(event)

        # Find the created file
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        assert len(csv_files) == 1, "Should create exactly one CSV file"

        # Read and verify contents
        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Should have header row and one data row
            assert len(rows) == 1

            # Verify header fields
            assert reader.fieldnames == disk.CSV_FIELDS

            # Verify data
            assert rows[0]["route_id"] == "Red"
            assert rows[0]["stop_id"] == "70001"
            assert rows[0]["event_type"] == "ARR"

    def test_write_event_appends_to_existing_file(self, temp_disk_dir):
        """Test writing multiple events appends to same file"""
        event1 = {
            "service_date": "2024-01-15",
            "route_id": "Red",
            "trip_id": "trip_123",
            "direction_id": 0,
            "stop_id": "70001",
            "stop_sequence": 5,
            "vehicle_id": "0",
            "vehicle_label": "1234",
            "event_type": "ARR",
            "event_time": datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 300.0,
            "scheduled_tt": 120,
            "vehicle_consist": "1234",
            "occupancy_status": None,
            "occupancy_percentage": None,
        }

        event2 = {
            "service_date": "2024-01-15",
            "route_id": "Red",
            "trip_id": "trip_456",
            "direction_id": 0,
            "stop_id": "70001",
            "stop_sequence": 3,
            "vehicle_id": "0",
            "vehicle_label": "5678",
            "event_type": "DEP",
            "event_time": datetime.datetime(2024, 1, 15, 10, 35, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 300.0,
            "scheduled_tt": 180,
            "vehicle_consist": "5678",
            "occupancy_status": "MANY_SEATS_AVAILABLE",
            "occupancy_percentage": None,
        }

        # Write both events
        disk.write_event(event1)
        disk.write_event(event2)

        # Find the created file
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        assert len(csv_files) == 1, "Should create only one CSV file"

        # Read and verify contents
        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Should have two data rows
            assert len(rows) == 2

            # Verify first event
            assert rows[0]["trip_id"] == "trip_123"
            assert rows[0]["event_type"] == "ARR"

            # Verify second event
            assert rows[1]["trip_id"] == "trip_456"
            assert rows[1]["event_type"] == "DEP"

    def test_write_event_creates_partitioned_directories(self, temp_disk_dir):
        """Test that events are written to correct partitioned directory structure"""
        event = {
            "service_date": "2024-03-20",
            "route_id": "Orange",
            "trip_id": "trip_789",
            "direction_id": 1,
            "stop_id": "70002",
            "stop_sequence": 8,
            "vehicle_id": "0",
            "vehicle_label": "9999",
            "event_type": "ARR",
            "event_time": datetime.datetime(2024, 3, 20, 15, 45, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 240.0,
            "scheduled_tt": 90,
            "vehicle_consist": "9999",
            "occupancy_status": None,
            "occupancy_percentage": None,
        }

        disk.write_event(event)

        # Verify directory structure exists
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        assert len(csv_files) == 1

        # Check path structure
        # Note: For rapid transit (Orange), path is daily-rapid-data/{stop_id}/Year=.../Month=.../Day=...
        file_path = str(csv_files[0])
        assert "daily-rapid-data" in file_path  # mode type
        assert "70002" in file_path  # stop_id (for rapid transit, no route-direction)
        assert "Year=2024" in file_path
        assert "Month=3" in file_path
        assert "Day=20" in file_path

    def test_write_event_different_stops_create_different_files(self, temp_disk_dir):
        """Test that events at different stops create separate files"""
        event_stop1 = {
            "service_date": "2024-01-15",
            "route_id": "Red",
            "trip_id": "trip_123",
            "direction_id": 0,
            "stop_id": "70001",
            "stop_sequence": 5,
            "vehicle_id": "0",
            "vehicle_label": "1234",
            "event_type": "ARR",
            "event_time": datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 300.0,
            "scheduled_tt": 120,
            "vehicle_consist": "1234",
            "occupancy_status": None,
            "occupancy_percentage": None,
        }

        event_stop2 = {
            "service_date": "2024-01-15",
            "route_id": "Red",
            "trip_id": "trip_123",
            "direction_id": 0,
            "stop_id": "70002",  # Different stop
            "stop_sequence": 6,
            "vehicle_id": "0",
            "vehicle_label": "1234",
            "event_type": "DEP",
            "event_time": datetime.datetime(2024, 1, 15, 10, 32, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 300.0,
            "scheduled_tt": 120,
            "vehicle_consist": "1234",
            "occupancy_status": None,
            "occupancy_percentage": None,
        }

        disk.write_event(event_stop1)
        disk.write_event(event_stop2)

        # Should create two separate files (one per stop)
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        assert len(csv_files) == 2, "Should create separate files for different stops"

        # Verify each file has correct data
        for csv_file in csv_files:
            with open(csv_file, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1, "Each file should have one event"

    def test_write_event_ignores_extra_fields(self, temp_disk_dir):
        """Test that extra fields in event dict are ignored"""
        event = {
            "service_date": "2024-01-15",
            "route_id": "Blue",
            "trip_id": "trip_blue",
            "direction_id": 0,
            "stop_id": "70003",
            "stop_sequence": 1,
            "vehicle_id": "0",
            "vehicle_label": "blue1",
            "event_type": "ARR",
            "event_time": datetime.datetime(2024, 1, 15, 11, 0, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": 360.0,
            "scheduled_tt": 150,
            "vehicle_consist": "blue1",
            "occupancy_status": None,
            "occupancy_percentage": None,
            # Extra fields that should be ignored
            "extra_field_1": "should_be_ignored",
            "extra_field_2": 12345,
        }

        disk.write_event(event)

        # Read file and verify extra fields were not written
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Verify only expected fields are present
            assert set(reader.fieldnames) == set(disk.CSV_FIELDS)
            assert "extra_field_1" not in rows[0]
            assert "extra_field_2" not in rows[0]

    def test_write_event_handles_none_values(self, temp_disk_dir):
        """Test that None values are written correctly to CSV"""
        event = {
            "service_date": "2024-01-15",
            "route_id": "Green-B",
            "trip_id": "trip_green",
            "direction_id": 1,
            "stop_id": "70004",
            "stop_sequence": 2,
            "vehicle_id": "0",
            "vehicle_label": "green1",
            "event_type": "DEP",
            "event_time": datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=EASTERN_TIME),
            "scheduled_headway": None,  # None value
            "scheduled_tt": None,  # None value
            "vehicle_consist": "green1",
            "occupancy_status": None,  # None value
            "occupancy_percentage": None,  # None value
        }

        disk.write_event(event)

        # Read and verify None values are handled
        csv_files = list(pathlib.Path(temp_disk_dir).rglob("events.csv"))
        with open(csv_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # CSV writes None as empty string
            assert rows[0]["scheduled_headway"] == ""
            assert rows[0]["occupancy_status"] == ""


class TestDiskConstants:
    """Test module constants"""

    def test_csv_filename(self):
        """Verify CSV filename constant"""
        assert disk.CSV_FILENAME == "events.csv"

    def test_csv_fields_contains_expected_fields(self):
        """Verify CSV fields list contains all expected fields"""
        expected_fields = [
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
            "vehicle_consist",
            "occupancy_status",
            "occupancy_percentage",
        ]

        assert disk.CSV_FIELDS == expected_fields
        assert len(disk.CSV_FIELDS) == 15

    def test_data_dir_is_pathlib_path(self):
        """Verify DATA_DIR is a pathlib.Path"""
        assert isinstance(disk.DATA_DIR, pathlib.Path)

    def test_state_filename(self):
        """Verify state filename constant"""
        assert disk.STATE_FILENAME == "state.json"
