"""Trip state management for tracking vehicle positions across events.

This module maintains in-memory state for active trips, allowing the system
to detect arrivals and departures by comparing current events to previous
state. State is persisted to disk to survive restarts and is automatically
cleaned up based on age and service date boundaries.

The state hierarchy is:
- TripsStateManager: Manages state across all routes (one per thread)
- RouteTripsState: Manages state for all trips on a single route
- TripState: State snapshot for a single trip (TypedDict)
"""

import json
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from typing import Dict, TypedDict, Optional
from ddtrace import tracer

from logger import set_up_logging
from disk import DATA_DIR
from util import EASTERN_TIME, get_current_service_date

logger = set_up_logging(__name__)


class TripState(TypedDict):
    """State snapshot for a single active trip.

    Captures the most recent known position and status of a vehicle on
    a specific trip, used to detect arrival and departure events by
    comparing successive updates.

    Attributes:
        stop_sequence: The current stop sequence number (how far into the trip).
        stop_id: The ID of the current or most recent stop.
        updated_at: Timestamp when this state was last updated.
        event_type: The last event type recorded ("ARR" or "DEP").
        vehicle_consist: Pipe-delimited car numbers for multi-car vehicles.
        occupancy_status: Pipe-delimited occupancy status per car, if available.
        occupancy_percentage: Pipe-delimited occupancy percentage per car
            (currently only available on Orange Line).
    """

    # How far into the trip are we?
    stop_sequence: int
    # What stop are we at?
    stop_id: str
    # When was this event received?
    updated_at: datetime
    # What type of event was this? (ARR or DEP)
    event_type: str
    # What vehicle numbers are included? Will be a pipe delimited string for vehicles with multiple carriages.
    vehicle_consist: str
    # Track Occupancy as available
    occupancy_status: str | None
    # Occupancy Percentage only available on Orange Line
    occupancy_percentage: str | None


def serialize_trip_state(trip_state: TripState) -> Dict[str, str]:
    """Serialize a TripState for JSON storage.

    Converts the datetime field to ISO 8601 string format for JSON
    serialization.

    Args:
        trip_state: The TripState to serialize.

    Returns:
        Dictionary with all fields, with updated_at as an ISO string.
    """
    return {
        **trip_state,
        "updated_at": trip_state["updated_at"].isoformat(),
    }


def deserialize_trip_state(trip_state: Dict[str, str]) -> TripState:
    """Deserialize a TripState from JSON storage.

    Converts the ISO 8601 string back to a datetime object.

    Args:
        trip_state: Dictionary loaded from JSON with updated_at as string.

    Returns:
        TripState with updated_at as a datetime object.
    """
    return {
        **trip_state,
        "updated_at": datetime.fromisoformat(trip_state["updated_at"]),
    }


def write_trips_state_file(route_id: str, state: "RouteTripsState") -> None:
    """Persist route trip state to disk.

    Writes the current state for all trips on a route to a JSON file,
    enabling recovery after restarts.

    Args:
        route_id: The route identifier (used as filename).
        state: The RouteTripsState object to persist.
    """
    trips_states_dir = DATA_DIR / "trip_states"
    trips_states_dir.mkdir(exist_ok=True)
    trip_file_path = trips_states_dir / f"{route_id}.json"
    trip_states = {trip_id: serialize_trip_state(trip_state) for trip_id, trip_state in state.trips.items()}
    file_contents = {
        "service_date": state.service_date.isoformat(),
        "trip_states": trip_states,
    }
    with open(trip_file_path, "w") as trip_file:
        trip_file.write(json.dumps(file_contents))


def read_trips_state_file(route_id: str) -> Optional[Dict]:
    """Load route trip state from disk.

    Reads previously persisted state for a route, if it exists.

    Args:
        route_id: The route identifier to load state for.

    Returns:
        Dictionary with 'trip_states' and 'service_date' keys if the file
        exists and is valid, None otherwise.
    """
    trip_file_path = DATA_DIR / "trip_states" / f"{route_id}.json"
    if trip_file_path.exists():
        with open(trip_file_path, "r") as trip_file:
            try:
                file_contents = json.load(trip_file)
                if "trip_states" in file_contents and "service_date" in file_contents:
                    trip_states = {
                        trip_id: deserialize_trip_state(trip_state)
                        for trip_id, trip_state in file_contents["trip_states"].items()
                    }
                    logger.info(f"Loaded {len(trip_states)} trip states for route {route_id}")
                    return {
                        "trip_states": trip_states,
                        "service_date": date.fromisoformat(file_contents["service_date"]),
                    }
            except json.decoder.JSONDecodeError:
                pass
    return None


@dataclass
class RouteTripsState:
    """Manages trip state for all active trips on a single route.

    Handles loading, saving, and cleanup of trip states. Automatically
    loads persisted state on initialization and cleans up stale entries.

    Attributes:
        route_id: The MBTA route identifier.
        service_date: The current service date for this state.
        trips: Dictionary mapping trip_id to TripState.
    """

    # Which route is this?
    route_id: str
    # Current service date (managed by this class)
    service_date: date = None
    # A dict to hold all the TripStates
    trips: Dict[str, TripState] = None

    def __post_init__(self):
        """Initialize by loading persisted state or creating empty state."""
        state_file = read_trips_state_file(self.route_id)
        if state_file:
            self.trips = state_file["trip_states"]
            self.service_date = state_file["service_date"]
            self._cleanup_trip_states()
        else:
            self.trips = {}
            self.service_date = get_current_service_date()

    @tracer.wrap()
    def set_trip_state(self, trip_id: str, trip_state: TripState) -> None:
        """Update the state for a trip.

        Performs cleanup of stale states before adding the new state,
        then persists the updated state to disk.

        Args:
            trip_id: The trip identifier to update.
            trip_state: The new state for the trip.
        """
        # Do cleanup first, before adding the new trip
        self._cleanup_trip_states()
        # Now add the new trip - it won't be cleared by purge
        self.trips[trip_id] = trip_state
        write_trips_state_file(self.route_id, self)

    @tracer.wrap()
    def get_trip_state(self, trip_id: str) -> Optional[TripState]:
        """Get the current state for a trip.

        Args:
            trip_id: The trip identifier to look up.

        Returns:
            A copy of the TripState if found, None otherwise.
        """
        trip = self.trips.get(trip_id)
        if trip:
            return {**trip}
        return None

    def _cleanup_trip_states(self) -> None:
        """Clean up trip states to prevent memory and CPU issues.

        Removes states that are either from a previous service date or
        older than 5 hours. Called before each state update.
        """
        self._cleanup_stale_trip_states()
        self._purge_trips_state_if_overnight()

    @tracer.wrap()
    def _cleanup_stale_trip_states(self, max_age_hours: int = 5) -> None:
        """Remove trip states older than the specified age threshold.

        Args:
            max_age_hours: Maximum age in hours for trip states. States
                older than this are removed. Defaults to 5 hours.
        """
        current_time = datetime.now(EASTERN_TIME)
        cutoff_time = current_time - timedelta(hours=max_age_hours)

        stale_trips = []
        for trip_id, trip_state in self.trips.items():
            if trip_state["updated_at"] < cutoff_time:
                stale_trips.append(trip_id)

        for trip_id in stale_trips:
            del self.trips[trip_id]

        if stale_trips:
            logger.info(f"Cleaned up {len(stale_trips)} stale trip states for route {self.route_id}")

    def _purge_trips_state_if_overnight(self) -> None:
        """Clear all trip states if the service date has changed.

        Called at the 3 AM service date boundary to start fresh for
        the new service day.
        """
        current_service_date = get_current_service_date()
        if self.service_date < current_service_date:
            logger.info(f"Purging trip state for route {self.route_id} on new service date {current_service_date}")
            self.service_date = current_service_date
            self.trips = {}


class TripsStateManager:
    """Top-level manager for trip state across multiple routes.

    Each event processing thread creates one TripsStateManager to track
    state for all routes it handles. Lazily creates RouteTripsState
    instances as needed.

    Attributes:
        route_states: Dictionary mapping route_id to RouteTripsState.
    """

    def __init__(self):
        """Initialize an empty state manager."""
        self.route_states = {}

    def set_trip_state(self, route_id: str, trip_id: str, trip_state: TripState) -> None:
        """Update the state for a trip on a route.

        Creates the RouteTripsState if this is the first trip for the route.

        Args:
            route_id: The route identifier.
            trip_id: The trip identifier.
            trip_state: The new state for the trip.
        """
        if route_id not in self.route_states:
            self.route_states[route_id] = RouteTripsState(route_id)
        self.route_states[route_id].set_trip_state(trip_id, trip_state)

    def get_trip_state(self, route_id: str, trip_id: str) -> Optional[TripState]:
        """Get the current state for a trip on a route.

        Args:
            route_id: The route identifier.
            trip_id: The trip identifier.

        Returns:
            The TripState if found, None if the route or trip is unknown.
        """
        if route_id not in self.route_states:
            return None
        return self.route_states[route_id].get_trip_state(trip_id)
