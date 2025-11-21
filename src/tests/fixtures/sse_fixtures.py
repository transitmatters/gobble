"""SSE (Server-Sent Events) specific test fixtures.

These fixtures are used only by SSE client tests.
"""

import pytest


@pytest.fixture
def sse_client_config():
    """Configuration for SSE client tests.

    Provides standard test values for SSE initialization.
    """
    return {
        "api_key": "test_sse_key_mbta",
        "api_url": "https://api-v3.mbta.com/vehicles",
    }


@pytest.fixture
def sample_sse_event():
    """Sample SSE event in MBTA API format.

    Represents a vehicle update as received from MBTA v3 API via SSE.
    """
    return {
        "data": {
            "type": "vehicle",
            "id": "y1234",
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2024-01-15T10:30:00+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": "MANY_SEATS_AVAILABLE",
                "occupancy_percentage": 75,
                "carriages": []
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70001"}},
                "trip": {"data": {"id": "trip_123"}}
            }
        }
    }


@pytest.fixture
def sample_event_reset_sequence():
    """Sample SSE reset event containing list of updates.

    Reset events in MBTA SSE API contain a list of current vehicle states.
    """
    return [
        {
            "data": {
                "type": "vehicle",
                "id": "y1234",
                "attributes": {
                    "current_status": "STOPPED_AT",
                    "updated_at": "2024-01-15T10:30:00+00:00",
                    "current_stop_sequence": 5,
                    "direction_id": 0,
                    "label": "1234",
                    "occupancy_status": "MANY_SEATS_AVAILABLE",
                    "occupancy_percentage": 75,
                    "carriages": []
                },
                "relationships": {
                    "route": {"data": {"id": "Red"}},
                    "stop": {"data": {"id": "70001"}},
                    "trip": {"data": {"id": "trip_123"}}
                }
            }
        },
        {
            "data": {
                "type": "vehicle",
                "id": "y5678",
                "attributes": {
                    "current_status": "IN_TRANSIT_TO",
                    "updated_at": "2024-01-15T10:29:00+00:00",
                    "current_stop_sequence": 4,
                    "direction_id": 0,
                    "label": "5678",
                    "occupancy_status": "SEATS_AVAILABLE",
                    "occupancy_percentage": 50,
                    "carriages": []
                },
                "relationships": {
                    "route": {"data": {"id": "Red"}},
                    "stop": {"data": {"id": "70002"}},
                    "trip": {"data": {"id": "trip_456"}}
                }
            }
        }
    ]
