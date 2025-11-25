"""
GTFS-RT client for consuming VehiclePositions feeds and converting them to gobble's internal event format.
"""

import time
import requests
from typing import Set, Iterator, Optional, Dict, Any, Literal
from datetime import datetime, timezone
from google.transit import gtfs_realtime_pb2
from ddtrace import tracer
from urllib.parse import urlparse, parse_qs, urlencode

from config import CONFIG
from logger import set_up_logging

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

# GTFS-RT VehicleStopStatus enum mapping
VEHICLE_STOP_STATUS_MAP = {
    0: "INCOMING_AT",
    1: "STOPPED_AT",
    2: "IN_TRANSIT_TO",
}

# GTFS-RT OccupancyStatus enum mapping
OCCUPANCY_STATUS_MAP = {
    0: "EMPTY",
    1: "MANY_SEATS_AVAILABLE",
    2: "FEW_SEATS_AVAILABLE",
    3: "STANDING_ROOM_ONLY",
    4: "CRUSHED_STANDING_ROOM_ONLY",
    5: "FULL",
    6: "NOT_ACCEPTING_PASSENGERS",
    7: "NO_DATA_AVAILABLE",
    8: "NOT_BOARDABLE",
}


class GtfsRtClient:
    """Client for fetching and parsing GTFS-RT VehiclePositions feeds."""

    def __init__(
        self,
        feed_url: str,
        api_key: Optional[str] = None,
        polling_interval: int = 10,
        api_key_method: Literal["header", "query", "bearer", "none"] = "header",
        api_key_param_name: str = "X-API-KEY",
    ):
        """
        Initialize GTFS-RT client.

        Args:
            feed_url: URL of the GTFS-RT VehiclePositions feed
            api_key: Optional API key for authentication
            polling_interval: Seconds between polls (default: 10)
            api_key_method: How to pass the API key ("header", "query", "bearer", "none")
            api_key_param_name: Header name or query param name for the API key (default: "X-API-KEY")
        """
        self.api_key = api_key
        self.polling_interval = polling_interval
        self.api_key_method = api_key_method
        self.api_key_param_name = api_key_param_name
        self.session = requests.Session()  # Connection pooling

        # Cache previous vehicle positions for de-duplication
        # Key: trip_id, Value: event dict
        self._previous_positions: Dict[str, dict] = {}

        # Build the feed URL with authentication if needed
        self.feed_url = self._build_authenticated_url(feed_url)

        # Set headers for header-based or bearer authentication
        self._set_authentication_headers()

    def _build_authenticated_url(self, feed_url: str) -> str:
        """
        Build the feed URL with query parameter authentication if needed.

        Args:
            feed_url: The base feed URL

        Returns:
            The URL with query parameter added if using query method
        """
        # Only add query parameter if using query method and have an API key
        if self.api_key_method == "query" and self.api_key:
            parsed = urlparse(feed_url)
            params = parse_qs(parsed.query)
            # Add API key parameter
            params[self.api_key_param_name] = [self.api_key]
            new_query = urlencode(params, doseq=True)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
        return feed_url

    def _set_authentication_headers(self) -> None:
        """Set up authentication headers based on the authentication method."""
        if not self.api_key:
            return

        if self.api_key_method == "header":
            self.session.headers.update({self.api_key_param_name: self.api_key})
        elif self.api_key_method == "bearer":
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _has_position_changed(self, trip_id: str, new_event: dict) -> bool:
        """
        Check if vehicle position has meaningfully changed since last poll.

        Args:
            trip_id: The trip ID to check
            new_event: The new event to compare

        Returns:
            True if position has changed in a meaningful way, False otherwise
        """
        if trip_id not in self._previous_positions:
            return True

        prev = self._previous_positions[trip_id]

        # Compare key fields that indicate meaningful changes
        # Check if we've moved to a different stop
        prev_stop = prev["relationships"]["stop"]["data"]
        new_stop = new_event["relationships"]["stop"]["data"]
        if prev_stop != new_stop:
            return True

        # Check if current status changed (e.g., IN_TRANSIT_TO -> STOPPED_AT)
        if (
            prev["attributes"]["current_status"]
            != new_event["attributes"]["current_status"]
        ):
            return True

        # Check if stop sequence changed (vehicle progressed through the route)
        if (
            prev["attributes"]["current_stop_sequence"]
            != new_event["attributes"]["current_stop_sequence"]
        ):
            return True

        # Check if occupancy status changed
        if (
            prev["attributes"]["occupancy_status"]
            != new_event["attributes"]["occupancy_status"]
        ):
            return True

        # Check if carriages changed (for multi-car consists)
        if prev["attributes"]["carriages"] != new_event["attributes"]["carriages"]:
            return True

        # No meaningful changes detected
        return False

    @tracer.wrap()
    def fetch_vehicle_positions(self) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        """
        Fetch and parse GTFS-RT VehiclePositions feed.

        Returns:
            Parsed FeedMessage or None on error
        """
        try:
            response = self.session.get(self.feed_url, timeout=30)
            response.raise_for_status()

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            logger.debug(f"Fetched {len(feed.entity)} entities from GTFS-RT feed")
            return feed

        except requests.exceptions.RequestException as e:
            logger.error("Failed to fetch GTFS-RT feed from %s: %s", self.feed_url, e)
            return None
        except Exception as e:
            logger.error("Failed to parse GTFS-RT feed: %s", e)
            return None

    @tracer.wrap()
    def poll_events(self, routes_filter: Set[str]) -> Iterator[dict]:
        """
        Continuously poll GTFS-RT feed and yield events in gobble's internal format.
        Only yields events when vehicle positions have meaningfully changed since last poll.

        Args:
            routes_filter: Set of route IDs to filter for

        Yields:
            Event dicts in gobble's internal format (only when changes detected)
        """
        while True:
            feed = self.fetch_vehicle_positions()

            if feed is not None:
                current_trip_ids = set()

                for entity in feed.entity:
                    if entity.HasField("vehicle"):
                        vehicle = entity.vehicle

                        # Filter by route
                        if vehicle.trip.route_id in routes_filter:
                            event = convert_vehicle_position_to_event(vehicle)
                            if event is not None:
                                trip_id = event["relationships"]["trip"]["data"]["id"]
                                current_trip_ids.add(trip_id)

                                # Only yield if position has changed
                                if self._has_position_changed(trip_id, event):
                                    logger.debug(
                                        f"Position changed for trip {trip_id}, yielding event"
                                    )
                                    yield event

                                # Update cached position
                                self._previous_positions[trip_id] = event

                # Clean up stale trips that are no longer in the feed
                # (vehicles that have completed their trips)
                stale_trips = set(self._previous_positions.keys()) - current_trip_ids
                for trip_id in stale_trips:
                    logger.debug(f"Removing stale trip {trip_id} from cache")
                    del self._previous_positions[trip_id]

            # Wait before next poll
            time.sleep(self.polling_interval)

    def close(self):
        """Close the HTTP session."""
        self.session.close()


@tracer.wrap()
def convert_vehicle_position_to_event(
    vehicle: gtfs_realtime_pb2.VehiclePosition,
) -> Optional[dict]:
    """
    Convert GTFS-RT VehiclePosition to gobble's internal event format.

    Args:
        vehicle: GTFS-RT VehiclePosition message

    Returns:
        Event dict in gobble's internal format, or None if invalid
    """
    try:
        # Extract basic trip/route/stop information
        trip_id = vehicle.trip.trip_id if vehicle.trip.HasField("trip_id") else None
        route_id = vehicle.trip.route_id if vehicle.trip.HasField("route_id") else None
        stop_id = vehicle.stop_id if vehicle.HasField("stop_id") else None
        direction_id = (
            vehicle.trip.direction_id if vehicle.trip.HasField("direction_id") else 0
        )

        # Skip if missing critical fields
        if not trip_id or not route_id:
            logger.debug("Skipping vehicle position with missing trip_id or route_id")
            return None

        # Extract current status
        current_status = VEHICLE_STOP_STATUS_MAP.get(
            vehicle.current_status, "IN_TRANSIT_TO"
        )

        # Extract timestamp (GTFS-RT uses Unix epoch seconds)
        if vehicle.HasField("timestamp"):
            updated_at = datetime.fromtimestamp(vehicle.timestamp, tz=timezone.utc)
        else:
            # Use current time if timestamp not provided
            updated_at = datetime.now(timezone.utc)

        # Convert to ISO format string
        updated_at_iso = updated_at.isoformat()

        # Extract current stop sequence
        current_stop_sequence = (
            vehicle.current_stop_sequence
            if vehicle.HasField("current_stop_sequence")
            else 0
        )

        # Extract vehicle label
        vehicle_label = (
            vehicle.vehicle.label
            if vehicle.vehicle.HasField("label")
            else vehicle.vehicle.id
        )

        # Extract occupancy information
        occupancy_status = None
        occupancy_percentage = None

        if vehicle.HasField("occupancy_status"):
            occupancy_status = OCCUPANCY_STATUS_MAP.get(
                vehicle.occupancy_status, "NO_DATA_AVAILABLE"
            )

        if vehicle.HasField("occupancy_percentage"):
            occupancy_percentage = vehicle.occupancy_percentage

        carriages = []

        if len(vehicle.multi_carriage_details) > 0:
            # Use per-carriage details when available
            for carriage in vehicle.multi_carriage_details:
                carriage_data: Dict[str, Any] = {
                    "id": None,
                    "label": None,
                    "occupancy_status": None,
                    "occupancy_percentage": None,
                    "carriage_sequence": None,
                }
                # Add carriage ID if present
                if carriage.HasField("id"):
                    carriage_data["id"] = carriage.id

                # Add label if present
                if carriage.HasField("label"):
                    carriage_data["label"] = carriage.label

                # Map occupancy status to human-readable string
                if carriage.HasField("occupancy_status"):
                    carriage_data["occupancy_status"] = OCCUPANCY_STATUS_MAP.get(
                        carriage.occupancy_status, "NO_DATA_AVAILABLE"
                    )

                # Add occupancy percentage if present and valid (not -1)
                if (
                    carriage.HasField("occupancy_percentage")
                    and carriage.occupancy_percentage >= 0
                ):
                    carriage_data["occupancy_percentage"] = (
                        carriage.occupancy_percentage
                    )

                # Add carriage sequence (position in train)
                if carriage.HasField("carriage_sequence"):
                    carriage_data["carriage_sequence"] = carriage.carriage_sequence

                carriages.append(carriage_data)

        # Build event dict in gobble's expected format
        event = {
            "attributes": {
                "current_status": current_status,
                "updated_at": updated_at_iso,
                "current_stop_sequence": current_stop_sequence,
                "direction_id": direction_id,
                "label": vehicle_label,
                "occupancy_status": occupancy_status,
                "occupancy_percentage": occupancy_percentage,
                "carriages": carriages,
            },
            "relationships": {
                "route": {"data": {"id": route_id}},
                "stop": {"data": {"id": stop_id} if stop_id else None},
                "trip": {"data": {"id": trip_id}},
            },
        }

        return event

    except Exception as e:
        logger.error("Failed to convert vehicle position to event: %s", e)
        return None


def create_gtfs_rt_client(config: dict) -> GtfsRtClient:
    """
    Factory function to create a GTFS-RT client from configuration.

    Args:
        config: Configuration dict with gtfs_rt settings

    Returns:
        Configured GtfsRtClient instance
    """
    gtfs_rt_config = config.get("gtfs_rt", {})
    feed_url = gtfs_rt_config.get("feed_url")
    api_key = gtfs_rt_config.get("api_key")
    polling_interval = gtfs_rt_config.get("polling_interval", 10)
    api_key_method = gtfs_rt_config.get("api_key_method", "header")
    api_key_param_name = gtfs_rt_config.get("api_key_param_name", "X-API-KEY")

    if not feed_url:
        raise ValueError("GTFS-RT feed_url must be configured")

    return GtfsRtClient(
        feed_url=feed_url,
        api_key=api_key,
        polling_interval=polling_interval,
        api_key_method=api_key_method,
        api_key_param_name=api_key_param_name,
    )
