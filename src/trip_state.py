import json
import os
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from typing import Dict, TypedDict, Optional, Tuple
from ddtrace import tracer

from logger import set_up_logging
from disk import DATA_DIR
from util import EASTERN_TIME, get_current_service_date

logger = set_up_logging(__name__)

# Write a trip's updated_at to disk at least this often, even if nothing else about the trip changed.
# Everything else is written as soon as it changes, so a restart only ever loses this much of updated_at.
PERSIST_UPDATED_AT_EVERY = timedelta(seconds=60)


class TripState(TypedDict):
    """
    Holds the current state of a single trip
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
    # Commuter Rail: whether we've recorded this trip's arrival at its last stop
    terminal_arrival_written: bool


def serialize_trip_state(trip_state: TripState) -> Dict[str, str]:
    return {
        **trip_state,
        "updated_at": trip_state["updated_at"].isoformat(),
    }


def deserialize_trip_state(trip_state: Dict[str, str]) -> TripState:
    return {
        **trip_state,
        "updated_at": datetime.fromisoformat(trip_state["updated_at"]),
    }


def write_trips_state_file(route_id: str, state: "RouteTripsState") -> None:
    trips_states_dir = DATA_DIR / "trip_states"
    trips_states_dir.mkdir(parents=True, exist_ok=True)
    trip_file_path = trips_states_dir / f"{route_id}.json"
    trip_states = {trip_id: serialize_trip_state(trip_state) for trip_id, trip_state in state.trips.items()}
    file_contents = {
        "service_date": state.service_date.isoformat(),
        "trip_states": trip_states,
    }
    # Write a temp file and rename it over the old one, so a crash mid-write never leaves a truncated file
    tmp_file_path = trips_states_dir / f"{route_id}.json.tmp"
    with open(tmp_file_path, "w") as trip_file:
        trip_file.write(json.dumps(file_contents))
    os.replace(tmp_file_path, trip_file_path)


def read_trips_state_file(route_id: str) -> Dict[str, TripState]:
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
    """
    Manages the state for all trips on a route
    """

    # Which route is this?
    route_id: str
    # Current service date (managed by this class)
    service_date: date = None
    # A dict to hold all the TripStates
    trips: Dict[str, TripState] = None

    def __post_init__(self):
        # Whether memory holds changes the state file doesn't
        self._unsaved_changes = False
        state_file = read_trips_state_file(self.route_id)
        if state_file:
            self.trips = state_file["trip_states"]
            self.service_date = state_file["service_date"]
            self._unsaved_changes = self._cleanup_trip_states()
        else:
            self.trips = {}
            self.service_date = get_current_service_date()
        # Each trip's updated_at as of the last time the state file was written
        self._persisted_updated_at = {trip_id: trip["updated_at"] for trip_id, trip in self.trips.items()}

    @tracer.wrap()
    def set_trip_state(self, trip_id: str, trip_state: TripState) -> None:
        # Do cleanup first, before adding the new trip
        if self._cleanup_trip_states():
            self._unsaved_changes = True
        # Now add the new trip - it won't be cleared by purge
        previous = self.trips.get(trip_id)
        self.trips[trip_id] = trip_state

        # Most updates are a vehicle reporting the same stop again, which only moves updated_at.
        # Write right away when anything else changes, and only every so often when just updated_at does.
        if previous is None or _without_updated_at(previous) != _without_updated_at(trip_state):
            self._unsaved_changes = True
        else:
            persisted_updated_at = self._persisted_updated_at.get(trip_id)
            if persisted_updated_at is None or abs(trip_state["updated_at"] - persisted_updated_at) >= (
                PERSIST_UPDATED_AT_EVERY
            ):
                self._unsaved_changes = True

        if self._unsaved_changes:
            write_trips_state_file(self.route_id, self)
            # Only after a successful write, so a failed one is retried on the next update
            self._persisted_updated_at = {trip_id: trip["updated_at"] for trip_id, trip in self.trips.items()}
            self._unsaved_changes = False

    def get_trip_state(self, trip_id: str) -> Optional[TripState]:
        trip = self.trips.get(trip_id)
        if trip:
            return {**trip}
        return None

    def _cleanup_trip_states(self) -> bool:
        """
        Clean up trip states to prevent memory/CPU issues.
        We don't care about yesterday's trip states, or ones older than 5 hours.
        Returns whether anything was removed.
        """
        removed_stale = self._cleanup_stale_trip_states()
        purged = self._purge_trips_state_if_overnight()
        return removed_stale or purged

    def _cleanup_stale_trip_states(self, max_age_hours: int = 5) -> bool:
        """
        Clean up stale trip states to prevent memory/CPU issues
        We don't want to keep too many trip states around, so we'll clean them up periodically.
        We'll keep the last 5 hours of trip states for each route at most.
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
        return len(stale_trips) > 0

    def _purge_trips_state_if_overnight(self) -> bool:
        current_service_date = get_current_service_date()
        if self.service_date < current_service_date:
            logger.info(f"Purging trip state for route {self.route_id} on new service date {current_service_date}")
            self.service_date = current_service_date
            self.trips = {}
            return True
        return False


def _without_updated_at(trip_state: TripState) -> dict:
    return {key: value for key, value in trip_state.items() if key != "updated_at"}


class TripsStateManager:
    """
    Manages the state for trips on many routes
    (typically all routes on each process_event thread)
    """

    def __init__(self):
        self.route_states = {}
        # vehicle id -> (route id, trip id) of the trip it's currently running
        self.vehicle_trips: Dict[str, Tuple[str, str]] = {}

    def vehicle_trip(self, vehicle_id: str) -> Optional[Tuple[str, str]]:
        return self.vehicle_trips.get(vehicle_id)

    def set_vehicle_trip(self, vehicle_id: str, route_id: str, trip_id: str) -> None:
        self.vehicle_trips[vehicle_id] = (route_id, trip_id)

    def pop_vehicle_trip(self, vehicle_id: str) -> Optional[Tuple[str, str]]:
        return self.vehicle_trips.pop(vehicle_id, None)

    def set_trip_state(self, route_id: str, trip_id: str, trip_state: TripState) -> None:
        if route_id not in self.route_states:
            self.route_states[route_id] = RouteTripsState(route_id)
        self.route_states[route_id].set_trip_state(trip_id, trip_state)

    def get_trip_state(self, route_id: str, trip_id: str) -> Optional[TripState]:
        if route_id not in self.route_states:
            return None
        return self.route_states[route_id].get_trip_state(trip_id)
