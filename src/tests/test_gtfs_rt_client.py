from datetime import datetime
from unittest.mock import Mock, patch
from google.transit import gtfs_realtime_pb2
import pytest

from gtfs_rt_client import (
    GtfsRtClient,
    convert_vehicle_position_to_event,
    VEHICLE_STOP_STATUS_MAP,
    OCCUPANCY_STATUS_MAP,
)


class TestGtfsRtClient:
    """Test suite for GTFS-RT client functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.feed_url = "https://example.com/gtfs-rt/vehicle-positions"
        self.api_key = "test_api_key"

    def test_client_initialization(self):
        """Test GTFS-RT client initialization with default header auth."""
        client = GtfsRtClient(feed_url=self.feed_url, api_key=self.api_key, polling_interval=15)

        assert client.feed_url == self.feed_url
        assert client.api_key == self.api_key
        assert client.polling_interval == 15
        assert client.api_key_method == "header"
        assert client.api_key_param_name == "X-API-KEY"
        assert "X-API-KEY" in client.session.headers
        assert client.session.headers["X-API-KEY"] == self.api_key

    def test_client_initialization_with_header_auth(self):
        """Test GTFS-RT client initialization with custom header authentication."""
        client = GtfsRtClient(
            feed_url=self.feed_url,
            api_key=self.api_key,
            api_key_method="header",
            api_key_param_name="api_key",
        )

        assert client.api_key_method == "header"
        assert client.api_key_param_name == "api_key"
        assert "api_key" in client.session.headers
        assert client.session.headers["api_key"] == self.api_key

    def test_client_initialization_with_query_auth(self):
        """Test GTFS-RT client initialization with query parameter authentication."""
        feed_url = "http://api.example.com/gtfs-rt"
        client = GtfsRtClient(
            feed_url=feed_url,
            api_key=self.api_key,
            api_key_method="query",
            api_key_param_name="api_key",
        )

        assert client.api_key_method == "query"
        assert client.api_key_param_name == "api_key"
        assert f"api_key={self.api_key}" in client.feed_url
        # Verify no header was set
        assert "X-API-KEY" not in client.session.headers

    def test_client_initialization_with_query_auth_existing_params(self):
        """Test query auth preserves existing URL parameters."""
        feed_url = "http://api.example.com/gtfs-rt?format=pb&agency=test"
        client = GtfsRtClient(
            feed_url=feed_url,
            api_key="secret123",
            api_key_method="query",
            api_key_param_name="key",
        )

        # Should have both existing params and new key
        assert "format=pb" in client.feed_url
        assert "agency=test" in client.feed_url
        assert "key=secret123" in client.feed_url

    def test_client_initialization_with_bearer_auth(self):
        """Test GTFS-RT client initialization with bearer token authentication."""
        client = GtfsRtClient(
            feed_url=self.feed_url,
            api_key=self.api_key,
            api_key_method="bearer",
        )

        assert client.api_key_method == "bearer"
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == f"Bearer {self.api_key}"

    def test_client_initialization_with_no_auth(self):
        """Test GTFS-RT client initialization with no authentication."""
        client = GtfsRtClient(
            feed_url=self.feed_url,
            api_key_method="none",
        )

        assert client.api_key_method == "none"
        assert "X-API-KEY" not in client.session.headers
        assert "Authorization" not in client.session.headers

    def test_client_initialization_no_api_key(self):
        """Test client initialization without API key."""
        client = GtfsRtClient(feed_url=self.feed_url)

        assert client.feed_url == self.feed_url
        assert client.api_key is None
        assert "X-API-KEY" not in client.session.headers

    @patch("gtfs_rt_client.requests.Session.get")
    def test_fetch_vehicle_positions_success(self, mock_get):
        """Test successful GTFS-RT feed fetch."""
        # Create a mock GTFS-RT feed
        feed = gtfs_realtime_pb2.FeedMessage()  # type: ignore

        # Add required header
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET  # type: ignore
        feed.header.timestamp = 1699999999

        # Add entity
        entity = feed.entity.add()
        entity.id = "1"
        vehicle = entity.vehicle
        vehicle.trip.trip_id = "test_trip"
        vehicle.trip.route_id = "Red"
        vehicle.stop_id = "70061"
        vehicle.current_status = 1  # STOPPED_AT
        vehicle.timestamp = 1699999999

        # Mock the response
        mock_response = Mock()
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = GtfsRtClient(feed_url=self.feed_url)
        result = client.fetch_vehicle_positions()

        assert result is not None
        assert len(result.entity) == 1
        assert result.entity[0].vehicle.trip.trip_id == "test_trip"

    @patch("gtfs_rt_client.requests.Session.get")
    def test_fetch_vehicle_positions_network_error(self, mock_get):
        """Test GTFS-RT feed fetch with network error."""
        import requests

        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        client = GtfsRtClient(feed_url=self.feed_url)
        result = client.fetch_vehicle_positions()

        assert result is None

    def test_convert_vehicle_position_basic(self):
        """Test basic vehicle position conversion."""
        # Create a GTFS-RT VehiclePosition
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_123"
        vehicle.trip.route_id = "Red"
        vehicle.trip.direction_id = 0
        vehicle.stop_id = "70061"
        vehicle.current_status = 2  # IN_TRANSIT_TO
        vehicle.current_stop_sequence = 10
        vehicle.vehicle.label = "1234"
        vehicle.timestamp = 1699999999

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        assert event["relationships"]["trip"]["data"]["id"] == "trip_123"
        assert event["relationships"]["route"]["data"]["id"] == "Red"
        assert event["relationships"]["stop"]["data"]["id"] == "70061"
        assert event["attributes"]["current_status"] == "IN_TRANSIT_TO"
        assert event["attributes"]["direction_id"] == 0
        assert event["attributes"]["current_stop_sequence"] == 10
        assert event["attributes"]["label"] == "1234"

    def test_convert_vehicle_position_with_occupancy(self):
        """Test vehicle position conversion with occupancy data."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_456"
        vehicle.trip.route_id = "Orange"
        vehicle.stop_id = "70001"
        vehicle.current_status = 1  # STOPPED_AT
        vehicle.current_stop_sequence = 5
        vehicle.vehicle.label = "5678"
        vehicle.timestamp = 1699999999
        vehicle.occupancy_status = 2  # FEW_SEATS_AVAILABLE
        vehicle.occupancy_percentage = 75

        # TODO: Convert this to a utility function so that we can generate Protobufs for testing
        # Add multi-carriage details
        carriage1 = vehicle.multi_carriage_details.add()
        carriage1.id = "carriage_1"
        carriage1.label = "Car 1"
        carriage1.occupancy_status = 2  # FEW_SEATS_AVAILABLE
        carriage1.occupancy_percentage = 75
        carriage1.carriage_sequence = 1

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        assert event["attributes"]["occupancy_status"] == "FEW_SEATS_AVAILABLE"
        assert len(event["attributes"]["carriages"]) == 1
        assert event["attributes"]["carriages"][0]["occupancy_status"] == "FEW_SEATS_AVAILABLE"
        assert event["attributes"]["carriages"][0]["occupancy_percentage"] == 75

    def test_convert_vehicle_position_missing_trip_id(self):
        """Test vehicle position conversion with missing trip_id."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.route_id = "Red"
        vehicle.stop_id = "70061"
        # No trip_id set

        event = convert_vehicle_position_to_event(vehicle)

        # Should return None for invalid data
        assert event is None

    def test_convert_vehicle_position_missing_route_id(self):
        """Test vehicle position conversion with missing route_id."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_123"
        vehicle.stop_id = "70061"
        # No route_id set

        event = convert_vehicle_position_to_event(vehicle)

        # Should return None for invalid data
        assert event is None

    def test_convert_vehicle_position_no_stop_id(self):
        """Test vehicle position conversion without stop_id (valid for in-transit)."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_789"
        vehicle.trip.route_id = "Blue"
        vehicle.current_status = 2  # IN_TRANSIT_TO
        vehicle.current_stop_sequence = 3
        vehicle.vehicle.label = "9012"
        vehicle.timestamp = 1699999999
        # No stop_id - vehicle might be between stops

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        assert event["relationships"]["stop"]["data"] is None

    def test_convert_vehicle_position_no_timestamp(self):
        """Test vehicle position conversion without timestamp (should use current time)."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_999"
        vehicle.trip.route_id = "Green-B"
        vehicle.stop_id = "70151"
        vehicle.current_status = 1  # STOPPED_AT
        vehicle.current_stop_sequence = 7
        vehicle.vehicle.label = "3456"
        # No timestamp set

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        # Should have a timestamp (current time)
        assert "updated_at" in event["attributes"]
        assert event["attributes"]["updated_at"] is not None

    def test_convert_vehicle_position_vehicle_id_fallback(self):
        """Test vehicle position uses vehicle.id when label is not provided."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_111"
        vehicle.trip.route_id = "1"  # Bus route
        vehicle.stop_id = "1"
        vehicle.current_status = 2
        vehicle.current_stop_sequence = 2
        vehicle.vehicle.id = "vehicle_id_123"
        # No vehicle.label set
        vehicle.timestamp = 1699999999

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        # Should use vehicle.id as fallback
        assert event["attributes"]["label"] == "vehicle_id_123"

    def test_vehicle_stop_status_map_coverage(self):
        """Test all GTFS-RT VehicleStopStatus values are mapped."""
        # GTFS-RT spec defines these statuses
        assert VEHICLE_STOP_STATUS_MAP[0] == "INCOMING_AT"
        assert VEHICLE_STOP_STATUS_MAP[1] == "STOPPED_AT"
        assert VEHICLE_STOP_STATUS_MAP[2] == "IN_TRANSIT_TO"

    def test_occupancy_status_map_coverage(self):
        """Test all GTFS-RT OccupancyStatus values are mapped."""
        # Verify key occupancy statuses are mapped
        assert OCCUPANCY_STATUS_MAP[0] == "EMPTY"
        assert OCCUPANCY_STATUS_MAP[1] == "MANY_SEATS_AVAILABLE"
        assert OCCUPANCY_STATUS_MAP[2] == "FEW_SEATS_AVAILABLE"
        assert OCCUPANCY_STATUS_MAP[3] == "STANDING_ROOM_ONLY"
        assert OCCUPANCY_STATUS_MAP[4] == "CRUSHED_STANDING_ROOM_ONLY"
        assert OCCUPANCY_STATUS_MAP[5] == "FULL"
        assert OCCUPANCY_STATUS_MAP[6] == "NOT_ACCEPTING_PASSENGERS"

    def test_timestamp_conversion_to_iso_format(self):
        """Test that Unix timestamps are correctly converted to ISO format."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_time_test"
        vehicle.trip.route_id = "Red"
        vehicle.stop_id = "70061"
        vehicle.current_status = 1
        vehicle.current_stop_sequence = 1
        vehicle.vehicle.label = "1111"
        # November 14, 2023 22:13:19 UTC
        vehicle.timestamp = 1699999999

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        updated_at = event["attributes"]["updated_at"]
        # Should be valid ISO format string
        parsed_dt = datetime.fromisoformat(updated_at)
        assert parsed_dt.year == 2023
        assert parsed_dt.month == 11
        assert parsed_dt.day == 14

    def test_direction_id_defaults_to_zero(self):
        """Test that direction_id defaults to 0 when not provided."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_dir_test"
        vehicle.trip.route_id = "Red"
        vehicle.stop_id = "70061"
        vehicle.current_status = 1
        vehicle.current_stop_sequence = 1
        vehicle.vehicle.label = "2222"
        vehicle.timestamp = 1699999999
        # No direction_id set

        event = convert_vehicle_position_to_event(vehicle)

        assert event is not None
        assert event["attributes"]["direction_id"] == 0

    def test_convert_vehicle_position_event_structure_matches_sse(self):
        """Test that converted event structure matches SSE API format."""
        vehicle = gtfs_realtime_pb2.VehiclePosition()  # type: ignore
        vehicle.trip.trip_id = "trip_struct_test"
        vehicle.trip.route_id = "Red"
        vehicle.trip.direction_id = 1
        vehicle.stop_id = "70061"
        vehicle.current_status = 1  # STOPPED_AT
        vehicle.current_stop_sequence = 15
        vehicle.vehicle.label = "3333"
        vehicle.timestamp = 1699999999
        vehicle.occupancy_status = 1  # MANY_SEATS_AVAILABLE

        event = convert_vehicle_position_to_event(vehicle)
        if event:
            # Verify structure matches what event.py expects
            assert "attributes" in event
            assert "relationships" in event

            # Attributes
            assert "current_status" in event["attributes"]
            assert "updated_at" in event["attributes"]
            assert "current_stop_sequence" in event["attributes"]
            assert "direction_id" in event["attributes"]
            assert "label" in event["attributes"]
            assert "occupancy_status" in event["attributes"]
            assert "carriages" in event["attributes"]

            # Relationships
            assert "route" in event["relationships"]
            assert "stop" in event["relationships"]
            assert "trip" in event["relationships"]
            assert "data" in event["relationships"]["route"]
            assert "data" in event["relationships"]["stop"]
            assert "data" in event["relationships"]["trip"]
            assert "id" in event["relationships"]["route"]["data"]
            assert "id" in event["relationships"]["stop"]["data"]
            assert "id" in event["relationships"]["trip"]["data"]

    def test_deduplication_first_position_always_yields(self):
        """Test that the first position for a trip is always yielded."""
        client = GtfsRtClient(feed_url=self.feed_url)

        # Create a test event
        event = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 1,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": None,
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_123"}},
            },
        }

        # First position should always be detected as changed
        assert client._has_position_changed("trip_123", event) is True

    def test_deduplication_identical_position_not_yielded(self):
        """Test that identical positions are not yielded."""
        client = GtfsRtClient(feed_url=self.feed_url)

        event = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": "MANY_SEATS_AVAILABLE",
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_456"}},
            },
        }

        # Cache the first position
        client._previous_positions["trip_456"] = event

        # Same position should not be detected as changed
        assert client._has_position_changed("trip_456", event) is False

    def test_deduplication_detects_stop_change(self):
        """Test that moving to a different stop is detected."""
        client = GtfsRtClient(feed_url=self.feed_url)

        old_event = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": None,
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_789"}},
            },
        }

        new_event = {
            **old_event,
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70063"}},  # Different stop
                "trip": {"data": {"id": "trip_789"}},
            },
        }

        client._previous_positions["trip_789"] = old_event

        # Different stop should be detected as changed
        assert client._has_position_changed("trip_789", new_event) is True

    def test_deduplication_detects_status_change(self):
        """Test that changing vehicle status is detected."""
        client = GtfsRtClient(feed_url=self.feed_url)

        old_event = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": None,
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_101"}},
            },
        }

        new_event = {
            **old_event,
            "attributes": {
                **old_event["attributes"],
                "current_status": "STOPPED_AT",  # Changed status
            },
        }

        client._previous_positions["trip_101"] = old_event

        # Different status should be detected as changed
        assert client._has_position_changed("trip_101", new_event) is True

    def test_deduplication_detects_stop_sequence_change(self):
        """Test that changing stop sequence is detected."""
        client = GtfsRtClient(feed_url=self.feed_url)

        old_event = {
            "attributes": {
                "current_status": "IN_TRANSIT_TO",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": None,
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_202"}},
            },
        }

        new_event = {
            **old_event,
            "attributes": {
                **old_event["attributes"],
                "current_stop_sequence": 6,  # Progressed to next stop
            },
        }

        client._previous_positions["trip_202"] = old_event

        # Different stop sequence should be detected as changed
        assert client._has_position_changed("trip_202", new_event) is True

    def test_deduplication_detects_occupancy_change(self):
        """Test that changing occupancy status is detected."""
        client = GtfsRtClient(feed_url=self.feed_url)

        old_event = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": "MANY_SEATS_AVAILABLE",
                "carriages": [],
            },
            "relationships": {
                "route": {"data": {"id": "Orange"}},
                "stop": {"data": {"id": "70001"}},
                "trip": {"data": {"id": "trip_303"}},
            },
        }

        new_event = {
            **old_event,
            "attributes": {
                **old_event["attributes"],
                "occupancy_status": "FEW_SEATS_AVAILABLE",  # Changed occupancy
            },
        }

        client._previous_positions["trip_303"] = old_event

        # Different occupancy should be detected as changed
        assert client._has_position_changed("trip_303", new_event) is True

    def test_deduplication_detects_carriage_change(self):
        """Test that changing carriage composition is detected."""
        client = GtfsRtClient(feed_url=self.feed_url)

        old_event = {
            "attributes": {
                "current_status": "STOPPED_AT",
                "updated_at": "2023-11-14T22:13:19+00:00",
                "current_stop_sequence": 5,
                "direction_id": 0,
                "label": "1234",
                "occupancy_status": None,
                "carriages": [
                    {
                        "label": "1234",
                        "occupancy_status": None,
                        "occupancy_percentage": None,
                    }
                ],
            },
            "relationships": {
                "route": {"data": {"id": "Red"}},
                "stop": {"data": {"id": "70061"}},
                "trip": {"data": {"id": "trip_404"}},
            },
        }

        new_event = {
            **old_event,
            "attributes": {
                **old_event["attributes"],
                "carriages": [
                    {
                        "label": "1234",
                        "occupancy_status": "EMPTY",
                        "occupancy_percentage": None,
                    },
                    {
                        "label": "5678",
                        "occupancy_status": "FULL",
                        "occupancy_percentage": None,
                    },
                ],  # More carriages
            },
        }

        client._previous_positions["trip_404"] = old_event

        # Different carriage configuration should be detected as changed
        assert client._has_position_changed("trip_404", new_event) is True

    def test_client_initializes_empty_cache(self):
        """Test that client starts with empty position cache."""
        client = GtfsRtClient(feed_url=self.feed_url)

        assert client._previous_positions == {}

    @pytest.mark.integration
    @patch("gtfs_rt_client.time.sleep")
    @patch("gtfs_rt_client.requests.Session.get")
    def test_poll_events_deduplication_integration(self, mock_get, mock_sleep):
        """Integration test for poll_events with de-duplication."""
        # Create two feeds with same vehicle in same position, then moved
        feed1 = gtfs_realtime_pb2.FeedMessage()  # type: ignore
        feed1.header.gtfs_realtime_version = "2.0"
        feed1.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET  # type: ignore
        feed1.header.timestamp = 1699999999

        entity1 = feed1.entity.add()
        entity1.id = "vehicle_1"
        entity1.vehicle.trip.trip_id = "trip_dedup_test"
        entity1.vehicle.trip.route_id = "Red"
        entity1.vehicle.stop_id = "70061"
        entity1.vehicle.current_status = 1  # STOPPED_AT
        entity1.vehicle.current_stop_sequence = 5
        entity1.vehicle.vehicle.label = "1234"
        entity1.vehicle.timestamp = 1699999999

        # Second feed - same position (should be deduplicated)
        feed2 = gtfs_realtime_pb2.FeedMessage()  # type: ignore
        feed2.header.gtfs_realtime_version = "2.0"
        feed2.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET  # type: ignore
        feed2.header.timestamp = 1700000009

        entity2 = feed2.entity.add()
        entity2.id = "vehicle_1"
        entity2.vehicle.trip.trip_id = "trip_dedup_test"
        entity2.vehicle.trip.route_id = "Red"
        entity2.vehicle.stop_id = "70061"  # Same stop
        entity2.vehicle.current_status = 1  # Same status
        entity2.vehicle.current_stop_sequence = 5  # Same sequence
        entity2.vehicle.vehicle.label = "1234"
        entity2.vehicle.timestamp = 1700000009

        # Third feed - vehicle moved (should NOT be deduplicated)
        feed3 = gtfs_realtime_pb2.FeedMessage()  # type: ignore
        feed3.header.gtfs_realtime_version = "2.0"
        feed3.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET  # type: ignore
        feed3.header.timestamp = 1700000019

        entity3 = feed3.entity.add()
        entity3.id = "vehicle_1"
        entity3.vehicle.trip.trip_id = "trip_dedup_test"
        entity3.vehicle.trip.route_id = "Red"
        entity3.vehicle.stop_id = "70063"  # Different stop!
        entity3.vehicle.current_status = 2  # IN_TRANSIT_TO
        entity3.vehicle.current_stop_sequence = 6
        entity3.vehicle.vehicle.label = "1234"
        entity3.vehicle.timestamp = 1700000019

        # Mock responses
        mock_responses = [
            Mock(content=feed1.SerializeToString(), raise_for_status=Mock()),
            Mock(content=feed2.SerializeToString(), raise_for_status=Mock()),
            Mock(content=feed3.SerializeToString(), raise_for_status=Mock()),
        ]
        mock_get.side_effect = mock_responses

        # Track number of polls
        poll_count = [0]

        def sleep_side_effect(_seconds):
            poll_count[0] += 1
            if poll_count[0] >= 3:
                raise KeyboardInterrupt()  # Exit the loop

        mock_sleep.side_effect = sleep_side_effect

        client = GtfsRtClient(feed_url=self.feed_url, polling_interval=10)

        events = []
        try:
            for event in client.poll_events({"Red"}):
                events.append(event)
        except KeyboardInterrupt:
            pass

        # Should get 2 events:
        # 1. First position (initial)
        # 2. Third position (vehicle moved)
        # Second position should be deduplicated
        assert len(events) == 2
        assert events[0]["relationships"]["stop"]["data"]["id"] == "70061"
        assert events[0]["attributes"]["current_status"] == "STOPPED_AT"
        assert events[1]["relationships"]["stop"]["data"]["id"] == "70063"
        assert events[1]["attributes"]["current_status"] == "IN_TRANSIT_TO"
