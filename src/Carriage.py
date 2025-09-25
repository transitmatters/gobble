import json
from gtfs_types import OccupancyStatus


class Carriage:
    def __init__(self, carriage_details):
        self.label: str = carriage_details.label
        self.carriage_sequence: int = carriage_details.carriage_sequence
        self.occupancy_status: OccupancyStatus = carriage_details.occupancy_status
        self.occupancy_percentage: float | None = None

    def Update(self, carriage_details):
        self.label: str = carriage_details.label
        self.carriage_sequence: int = carriage_details.carriage_sequence
        self.occupancy_status: OccupancyStatus = carriage_details.occupancy_status
        self.occupancy_percentage: float | None = None

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
