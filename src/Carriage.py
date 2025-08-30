import json
from gtfs_types import OccupancyStatus


class Carriage:
    def __init__(self, carriage_details):
        self.label: str = carriage_details.label
        self.carriage_sequence: int = carriage_details.carriage_sequence
        self.occupancy_status: list[OccupancyStatus] = [carriage_details.occupancy_status]

    def Update(self, carriage_details):
        self.occupancy_status.append(carriage_details.occupancy_status)

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
