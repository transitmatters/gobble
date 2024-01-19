import json
from datetime import date, datetime
from dataclasses import dataclass
from typing import Dict, TypedDict, Optional
from ddtrace import tracer


from disk import DATA_DIR
from util import get_current_service_date


class TripState(TypedDict):
    """
    Holds the current state of a single trip
    """

    # How far into the trip are we?
    stop_sequence: int
    # What stop are we at?
    stop_id: str
    # When was this event received (as a string)
    updated_at: datetime
    # What type of event was this? (ARR or DEP)
    event_type: str


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
    print(file_contents)
    with open(trip_file_path, "w") as trip_file:
        trip_file.write(json.dumps(file_contents))


def read_trips_state_file(route_id: str) -> Dict[str, TripState]:
    trip_file_path = DATA_DIR / "trip_states" / f"{route_id}.json"
    if trip_file_path.exists():
        with open(trip_file_path, "r") as trip_file:
            try:
                file_contents = json.load(trip_file)
                if "trip_states" in file_contents and "service_date" in file_contents:
                    return {
                        "trip_states": {
                            trip_id: deserialize_trip_state(trip_state)
                            for trip_id, trip_state in file_contents["trip_states"].items()
                        },
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
            self._purge_trips_state_if_overnight()
        else:
            self.trips = {}
            self.service_date = get_current_service_date()

    @tracer.wrap(name="update_trip_state")
    def set_trip_state(self, trip_id: str, trip_state: TripState) -> None:
        self.trips[trip_id] = trip_state
        write_trips_state_file(self.route_id, self)

    @tracer.wrap(name="get_trip_state")
    def get_trip_state(self, trip_id: str) -> Optional[TripState]:
        self._purge_trips_state_if_overnight()
        trip = self.trips.get(trip_id)
        if trip:
            return {**trip}
        return None

    def _purge_trips_state_if_overnight(self) -> None:
        current_service_date = get_current_service_date()
        if self.service_date < current_service_date:
            self.service_date = current_service_date
            self.trips = {}
        write_trips_state_file(self.route_id, self)


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
