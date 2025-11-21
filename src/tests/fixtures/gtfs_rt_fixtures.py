"""GTFS-RT specific test fixtures.

These fixtures are used only by GTFS-RT client tests.
"""

import pytest


@pytest.fixture
def gtfs_rt_client_config():
    """Configuration for GTFS-RT client tests.

    Provides standard test values for GTFS-RT initialization.
    """
    return {
        "feed_url": "https://example.com/gtfs-rt/vehicle-positions",
        "api_key": "test_gtfs_rt_key",
        "polling_interval": 10,
        "api_key_method": "header",
        "api_key_param_name": "X-API-KEY",
    }


@pytest.fixture
def sample_gtfs_rt_event():
    """Sample GTFS-RT event in standard internal format.

    Represents a vehicle position update from GTFS-RT source.
    """
    return {
        "attributes": {
            "current_status": "STOPPED_AT",
            "updated_at": "2024-01-15T10:30:00+00:00",
            "current_stop_sequence": 5,
            "direction_id": 0,
            "label": "1234",
            "occupancy_status": "MANY_SEATS_AVAILABLE",
            "occupancy_percentage": 75,
            "carriages": [],
        },
        "relationships": {
            "route": {"data": {"id": "Red"}},
            "stop": {"data": {"id": "70001"}},
            "trip": {"data": {"id": "trip_123"}},
        },
    }


@pytest.fixture(scope="session")
def basic_feed_message():
    """Session-scoped basic GTFS-RT FeedMessage protobuf.

    Creates a minimal valid feed with header and one vehicle entity.
    Reused across tests to avoid repeated protobuf construction.
    """
    from google.transit import gtfs_realtime_pb2

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET
    feed.header.timestamp = 1699999999

    entity = feed.entity.add()
    entity.id = "1"
    vehicle = entity.vehicle
    vehicle.trip.trip_id = "test_trip"
    vehicle.trip.route_id = "Red"
    vehicle.stop_id = "70061"
    vehicle.current_status = 1  # STOPPED_AT
    vehicle.timestamp = 1699999999

    return feed


@pytest.fixture(scope="session")
def vehicle_with_occupancy():
    """Session-scoped GTFS-RT VehiclePosition with occupancy data.

    Reused across tests testing occupancy handling.
    """
    from google.transit import gtfs_realtime_pb2

    vehicle = gtfs_realtime_pb2.VehiclePosition()
    vehicle.trip.trip_id = "trip_456"
    vehicle.trip.route_id = "Orange"
    vehicle.stop_id = "70001"
    vehicle.current_status = 1  # STOPPED_AT
    vehicle.current_stop_sequence = 5
    vehicle.vehicle.label = "5678"
    vehicle.timestamp = 1699999999
    vehicle.occupancy_status = 2  # FEW_SEATS_AVAILABLE
    vehicle.occupancy_percentage = 75
    return vehicle
