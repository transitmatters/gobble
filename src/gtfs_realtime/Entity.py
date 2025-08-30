import uuid
import json
import datetime
from datetime import date
import os
from Carriage import Carriage
import gtfs
import pandas as pd
from event import enrich_event
from util import service_date
import disk


# Event type mappings from the main gobble codebase
EVENT_TYPE_MAP = {
    "IN_TRANSIT_TO": "DEP",
    "STOPPED_AT": "ARR",
    "INCOMING_AT": "ARR",
}

# GTFS Realtime current_status integer mappings
# 0: "INCOMING_AT", 1: "STOPPED_AT", 2: "IN_TRANSIT_TO"
CURRENT_STATUS_MAP = {0: "ARR", 1: "ARR", 2: "DEP"}


class Entity:
    def __init__(self, entity):
        self.entity_id: str = entity.id

        # Static - We do not expect updates to this information
        self.direction_id: int = entity.vehicle.trip.direction_id
        self.label: str = entity.vehicle.vehicle.label
        # TODO: self.revenue = attributes.get("revenue", None)
        self.created: datetime.datetime = datetime.datetime.now()
        self.route_id: str = entity.vehicle.trip.route_id
        self.trip_id: str = entity.vehicle.trip.trip_id
        self.schedule_relationship: int = entity.vehicle.trip.schedule_relationship
        self.start_date: str = entity.vehicle.trip.start_date
        self.start_time: str = entity.vehicle.trip.start_time
        self.vehicle_id: str = entity.vehicle.vehicle.id
        self.vehicle_label: str = entity.vehicle.vehicle.label
        self.license_plate: str = entity.vehicle.vehicle.license_plate
        self.service_date: date = service_date(entity.vehicle.timestamp)

        # Temporal - we expect updates to this information
        self.bearing: float = entity.vehicle.position.bearing
        self.current_status: int = entity.vehicle.current_status
        self.odometer: float = entity.vehicle.position.odometer
        self.speed: float = entity.vehicle.position.speed
        self.stop_id: str = entity.vehicle.stop_id
        self.updated_at: str = datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat()
        self.current_stop_sequence: int = entity.vehicle.current_stop_sequence
        self.coordinates: list[float] = [entity.vehicle.position.longitude, entity.vehicle.position.latitude]
        self.occupancy_status: int = entity.vehicle.occupancy_status
        self.occupancy_percentage: float = entity.vehicle.occupancy_percentage
        self.congestion_level: int = entity.vehicle.congestion_level

        self.carriages: list[Carriage] = [Carriage(c) for c in entity.vehicle.multi_carriage_details]

    def update(self, entity):
        # Temporal
        self.bearing = entity.vehicle.position.bearing
        self.current_status = entity.vehicle.current_status
        self.current_stop_sequence = entity.vehicle.current_stop_sequence
        self.coordinates = [entity.vehicle.position.longitude, entity.vehicle.position.latitude]
        self.occupancy_status = entity.vehicle.occupancy_status
        self.occupancy_percentage = entity.vehicle.occupancy_percentage
        self.speed = entity.vehicle.position.speed
        self.odometer = entity.vehicle.position.odometer
        # TODO: need to convert to ISO 8601 format
        self.updated_at = datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat()
        self.stop_id = entity.vehicle.stop_id
        self.congestion_level = entity.vehicle.congestion_level

        self.carriages: list[Carriage] = [Carriage(c) for c in entity.vehicle.multi_carriage_details]

    def checkage(self):
        # checks age of object and returns age in seconds
        return (datetime.datetime.now() - self.created).total_seconds()

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    # TODO: convert f.write() to export to gobble format
    def save(self):

        gtfs_archive = gtfs.get_current_gtfs_archive()
        status_str = CURRENT_STATUS_MAP.get(self.current_status)
        # write the event here
        df = pd.DataFrame(
            [
                {
                    "service_date": service_date,
                    "route_id": self.route_id,
                    "trip_id": self.trip_id,
                    "direction_id": self.direction_id,
                    "stop_id": self.stop_id,
                    "stop_sequence": self.current_stop_sequence,
                    "vehicle_id": self.vehicle_id,
                    "vehicle_label": self.vehicle_label,
                    "event_type": status_str,
                    "event_time": self.updated_at,
                }
            ],
            index=[0],
        )
        event = enrich_event(df, gtfs_archive)
        disk.write_event(event)
