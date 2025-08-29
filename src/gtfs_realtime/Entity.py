import uuid
import json
import datetime
import os
from helpers.s3Uploader import upload_file
from helpers.setup_logger import logger


class Carriage:
    def __init__(self, carriage_details):
        self.label = carriage_details.label
        self.carriage_sequence = carriage_details.carriage_sequence
        self.occupancy_status = [carriage_details.occupancy_status]

    def Update(self, carriage_details):
        self.occupancy_status.append(carriage_details.occupancy_status)

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class Entity:
    def __init__(self, entity):
        self.entity_id = entity.id

        # Static
        self.direction_id = entity.vehicle.trip.direction_id
        self.label = entity.vehicle.vehicle.label
        # TODO: self.revenue = attributes.get("revenue", None)
        self.created = datetime.datetime.now()
        self.route_id = entity.vehicle.trip.route_id
        self.trip_id = entity.vehicle.trip.trip_id
        self.schedule_relationship = entity.vehicle.trip.schedule_relationship
        self.start_date = entity.vehicle.trip.start_date
        self.start_time = entity.vehicle.trip.start_time
        self.vehicle_id = entity.vehicle.vehicle.id
        self.vehicle_label = entity.vehicle.vehicle.label
        self.license_plate = entity.vehicle.vehicle.license_plate

        # Temporal
        self.bearing = [entity.vehicle.position.bearing]
        self.current_status = [entity.vehicle.current_status]
        self.odometer = [entity.vehicle.position.odometer]
        self.speed = [entity.vehicle.position.speed]
        self.stop_id = [entity.vehicle.stop_id]
        self.updated_at = [
            datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat()
        ]
        self.current_stop_sequence = [entity.vehicle.current_stop_sequence]
        self.coordinates = [
            [entity.vehicle.position.longitude, entity.vehicle.position.latitude]
        ]
        self.occupancy_status = [entity.vehicle.occupancy_status]
        self.occupancy_percentage = [entity.vehicle.occupancy_percentage]
        self.congestion_level = [entity.vehicle.congestion_level]

        self.carriages = [Carriage(c) for c in entity.vehicle.multi_carriage_details]

        # TODO: get multicarriage details
        # print(entity.vehicle.multi_carriage_details)
        # print(entity.vehicle.multi_carriage_details[0].label)
        # print(entity.vehicle.multi_carriage_details[0].carriage_sequence)
        # first two = static, third = temporal
        # print(entity.vehicle.multi_carriage_details[0].occupancy_status)

    def update(self, entity):
        # Temporal
        self.bearing.append(entity.vehicle.position.bearing)
        self.current_status.append(entity.vehicle.current_status)
        self.current_stop_sequence.append(entity.vehicle.current_stop_sequence)
        self.coordinates.append(
            [entity.vehicle.position.longitude, entity.vehicle.position.latitude]
        )
        self.occupancy_status.append(entity.vehicle.occupancy_status)
        self.occupancy_percentage.append(entity.vehicle.occupancy_percentage)
        self.speed.append(entity.vehicle.position.speed)
        self.odometer.append(entity.vehicle.position.odometer)
        # TODO: need to convert to ISO 8601 format
        self.updated_at.append(
            datetime.datetime.fromtimestamp(entity.vehicle.timestamp).isoformat()
        )
        self.stop_id.append(entity.vehicle.stop_id)
        self.congestion_level.append(entity.vehicle.congestion_level)

        for carriage in entity.vehicle.multi_carriage_details:
            carriage_obj = next(
                (c for c in self.carriages if c.label == carriage.label), None
            )
            if carriage_obj:
                carriage_obj.Update(carriage)

    def checkage(self):
        # checks age of object and returns age in seconds
        return (datetime.datetime.now() - self.created).total_seconds()

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def toMFJSON(self):
        # TODO: add carriage details
        # TODO: Need to update properties being written out
        dict_template = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "temporalGeometry": {
                        "type": "MovingPoint",
                        "coordinates": self.coordinates,
                        "datetimes": self.updated_at,
                        "interpolation": "Linear",
                    },
                    "properties": {
                        "trajectory_id": 0,
                        "entity_id": self.entity_id,
                        "direction_id": self.direction_id,
                        "label": self.label,
                        "trip_id": self.trip_id,
                        "route_id": self.route_id,
                        "schedule_relationship": self.schedule_relationship,
                        "trip_start_date": self.start_date,
                        "trip_start_time": self.start_time,
                        "vehicle_id": self.vehicle_id,
                        "vehicle_label": self.vehicle_label,
                        "license_plate": self.license_plate,
                    },
                    "temporalProperties": [
                        {
                            "datetimes": self.updated_at,
                            "bearing": {
                                "type": "Measure",
                                "values": self.bearing,
                                "interpolation": "Linear",
                            },
                            "current_status": {
                                "type": "Measure",
                                "values": self.current_status,
                                "interpolation": "Discrete",
                            },
                            "odometer": {
                                "type": "Measure",
                                "values": self.odometer,
                                "interpolation": "Discrete",
                            },
                            "speed": {
                                "type": "Measure",
                                "values": self.speed,
                                "interpolation": "Linear",
                            },
                            "stop_id": {
                                "type": "Measure",
                                "values": self.stop_id,
                                "interpolation": "Discrete",
                            },
                            "current_stop_sequence": {
                                "type": "Measure",
                                "values": self.current_stop_sequence,
                                "interpolation": "Discrete",
                            },
                            "occupancy_status": {
                                "type": "Measure",
                                "values": self.occupancy_status,
                                "interpolation": "Discrete",
                            },
                            "occupancy_percentage": {
                                "type": "Measure",
                                "values": self.occupancy_percentage,
                                "interpolation": "Discrete",
                            },
                            "congestion_level": {
                                "type": "Measure",
                                "values": self.congestion_level,
                                "interpolation": "Discrete",
                            },
                        }
                    ],
                }
            ],
        }
        for carriage in self.carriages:
            carriage_key = f"carriage_{carriage.carriage_sequence}_{carriage.label}"
            dict_template["features"][0]["temporalProperties"][0][carriage_key] = {
                "type": "Measure",
                "values": carriage.occupancy_status,
                "interpolation": "Discrete",
            }

        return json.dumps(
            dict_template,
            indent=4,
        )

    def save(self, file_path):
        isExist = os.path.exists(f"{file_path}/{self.route_id}")
        if isExist is False:
            os.makedirs(f"{file_path}/{self.route_id}", mode=0o777, exist_ok=False)
            with open(f"{file_path}/{self.route_id}/{uuid.uuid4()}.mfjson", "w") as f:
                f.write(self.toMFJSON())
        else:
            with open(f"{file_path}/{self.route_id}/{uuid.uuid4()}.mfjson", "w") as f:
                f.write(self.toMFJSON())

    def savetos3(self, bucket, file_path):
        logger.info(type(bucket))
        upload_file(self.toMFJSON(), bucket, f"{file_path}/{uuid.uuid4()}.mfjson")
