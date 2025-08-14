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
    trips_states_dir.mkdir(exist_ok=True)
    trip_file_path = trips_states_dir / f"{route_id}.json"
    trip_states = {trip_id: serialize_trip_state(trip_state) for trip_id, trip_state in state.trips.items()}
    file_contents = {
        "service_date": state.service_date.isoformat(),
        "trip_states": trip_states,
    }
    with open(trip_file_path, "w") as trip_file:
        trip_file.write(json.dumps(file_contents))


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
        # Do cleanup first, before adding the new trip
        self._cleanup_trip_states()
        # Now add the new trip - it won't be cleared by purge
        self.trips[trip_id] = trip_state
        write_trips_state_file(self.route_id, self)

    @tracer.wrap()
    def get_trip_state(self, trip_id: str) -> Optional[TripState]:
        trip = self.trips.get(trip_id)
        if trip:
            return {**trip}
        return None

    def _cleanup_trip_states(self) -> None:
        """
        Clean up trip states to prevent memory/CPU issues.
        We don't care about yesterday's trip states, or ones older than 5 hours.
        """
        self._cleanup_stale_trip_states()
        self._purge_trips_state_if_overnight()

    @tracer.wrap()
    def _cleanup_stale_trip_states(self, max_age_hours: int = 5) -> None:
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

    def _purge_trips_state_if_overnight(self) -> None:
        current_service_date = get_current_service_date()
        if self.service_date < current_service_date:
            logger.info(f"Purging trip state for route {self.route_id} on new service date {current_service_date}")
            self.service_date = current_service_date
            self.trips = {}


class TripsStateManager:
    """
    Manages the state for trips on many routes
    (typically all routes on each process_event thread)
    """

    def __init__(self):
        self.route_states = {}

    def set_trip_state(self, route_id: str, trip_id: str, trip_state: TripState) -> None:
        if route_id not in self.route_states:
            self.route_states[route_id] = RouteTripsState(route_id)
        self.route_states[route_id].set_trip_state(trip_id, trip_state)

    def get_trip_state(self, route_id: str, trip_id: str) -> Optional[TripState]:
        if route_id not in self.route_states:
            return None
        return self.route_states[route_id].get_trip_state(trip_id)
