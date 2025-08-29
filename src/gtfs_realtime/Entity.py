import uuid
import json
import datetime
import os
from Carriage import Carriage


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

        # Temporal - we expect updates to this information
        self.bearing: list[float] = [entity.vehicle.position.bearing]
        self.current_status: list[int] = [entity.vehicle.current_status]
        self.odometer: list[float] = [entity.vehicle.position.odometer]
        self.speed: list[float] = [entity.vehicle.position.speed]
        self.stop_id: list[str] = [entity.vehicle.stop_id]
        self.updated_at: list[str] = [datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat()]
        self.current_stop_sequence: list[int] = [entity.vehicle.current_stop_sequence]
        self.coordinates: list[list[float]] = [[entity.vehicle.position.longitude, entity.vehicle.position.latitude]]
        self.occupancy_status: list[int] = [entity.vehicle.occupancy_status]
        self.occupancy_percentage: list[float] = [entity.vehicle.occupancy_percentage]
        self.congestion_level: list[int] = [entity.vehicle.congestion_level]

        self.carriages: list[Carriage] = [Carriage(c) for c in entity.vehicle.multi_carriage_details]

    def update(self, entity):
        # Temporal
        self.bearing.append(entity.vehicle.position.bearing)
        self.current_status.append(entity.vehicle.current_status)
        self.current_stop_sequence.append(entity.vehicle.current_stop_sequence)
        self.coordinates.append([entity.vehicle.position.longitude, entity.vehicle.position.latitude])
        self.occupancy_status.append(entity.vehicle.occupancy_status)
        self.occupancy_percentage.append(entity.vehicle.occupancy_percentage)
        self.speed.append(entity.vehicle.position.speed)
        self.odometer.append(entity.vehicle.position.odometer)
        # TODO: need to convert to ISO 8601 format
        self.updated_at.append(datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat())
        self.stop_id.append(entity.vehicle.stop_id)
        self.congestion_level.append(entity.vehicle.congestion_level)

        for carriage in entity.vehicle.multi_carriage_details:
            carriage_obj = next((c for c in self.carriages if c.label == carriage.label), None)
            if carriage_obj:
                carriage_obj.Update(carriage)

    def checkage(self):
        # checks age of object and returns age in seconds
        return (datetime.datetime.now() - self.created).total_seconds()

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    # TODO: convert f.write() to export to gobble format
    def save(self, file_path):
        isExist = os.path.exists(f"{file_path}/{self.route_id}")
        if isExist is False:
            os.makedirs(f"{file_path}/{self.route_id}", mode=0o777, exist_ok=False)
            with open(f"{file_path}/{self.route_id}/{uuid.uuid4()}.mfjson", "w") as f:
                f.write("")
        else:
            with open(f"{file_path}/{self.route_id}/{uuid.uuid4()}.mfjson", "w") as f:
                f.write("")
