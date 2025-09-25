from Entity import Entity


class VehiclePositionFeed:
    def __init__(
        self,
        url,
        agency,
        timeout=30,
    ):
        self.entities: list[Entity] = []
        self.url: str = url
        self.agency: str = agency
        self.timeout: int = timeout

    def find_entity(self, entity_id):
        return next((e for e in self.entities if e.entity_id == entity_id), None)

    def updatetimeout(self, timeout):
        self.timeout = timeout
