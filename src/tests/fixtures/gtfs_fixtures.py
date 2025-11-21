"""Mock GTFS archive fixtures for testing.

These session-scoped fixtures provide reusable mock GTFS data to avoid
recreating mock DataFrames in every test function.
"""

import pytest
import pandas as pd
from unittest.mock import Mock
import sys
from pathlib import Path

# Add src to path to import gtfs module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import gtfs


@pytest.fixture(scope="session")
def mock_stops_df():
    """Session-scoped mock stops DataFrame.

    Used across multiple tests to represent GTFS stop data.
    """
    return pd.DataFrame(
        [
            {"stop_id": "70001", "stop_name": "Harvard Square"},
            {"stop_id": "70002", "stop_name": "Central Square"},
            {"stop_id": "70003", "stop_name": "Kendall Square"},
            {"stop_id": "70004", "stop_name": "Downtown Crossing"},
        ]
    )


@pytest.fixture(scope="session")
def mock_trips_df():
    """Session-scoped mock trips DataFrame.

    Used across multiple tests to represent GTFS trip data.
    """
    return pd.DataFrame(
        [
            {
                "route_id": "Red",
                "trip_id": "trip_123",
                "direction_id": 0,
                "trip_headsign": "Ashmont",
            },
            {
                "route_id": "Orange",
                "trip_id": "trip_456",
                "direction_id": 1,
                "trip_headsign": "Forest Hills",
            },
            {
                "route_id": "Blue",
                "trip_id": "trip_789",
                "direction_id": 0,
                "trip_headsign": "Bowdoin",
            },
        ]
    )


@pytest.fixture(scope="session")
def mock_stop_times_df():
    """Session-scoped mock stop_times DataFrame.

    Used across multiple tests to represent GTFS stop_times data.
    """
    return pd.DataFrame(
        [
            {
                "trip_id": "trip_123",
                "stop_id": "70001",
                "stop_sequence": 5,
                "arrival_time": pd.Timedelta(hours=10, minutes=30),
                "departure_time": pd.Timedelta(hours=10, minutes=30),
            },
            {
                "trip_id": "trip_123",
                "stop_id": "70002",
                "stop_sequence": 6,
                "arrival_time": pd.Timedelta(hours=10, minutes=35),
                "departure_time": pd.Timedelta(hours=10, minutes=35),
            },
        ]
    )


@pytest.fixture(scope="function")
def mock_gtfs_archive(mock_stops_df, mock_trips_df, mock_stop_times_df):
    """Function-scoped mock GtfsArchive.

    Creates a fresh mock for each test but reuses session-scoped
    DataFrames to avoid recreating them.
    """
    mock_archive = Mock(spec=gtfs.GtfsArchive)
    mock_archive.stops = mock_stops_df.copy()
    mock_archive.trips_by_route_id.return_value = mock_trips_df.copy()
    mock_archive.stop_times_by_route_id.return_value = mock_stop_times_df.copy()
    return mock_archive


@pytest.fixture(scope="session")
def empty_trips_df():
    """Session-scoped empty trips DataFrame for tests expecting no data."""
    return pd.DataFrame()


@pytest.fixture(scope="session")
def empty_stop_times_df():
    """Session-scoped empty stop_times DataFrame for tests expecting no data."""
    return pd.DataFrame()
