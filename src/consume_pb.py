from Entity import Entity
import datetime
from logger import set_up_logging
from ddtrace import tracer
from config import CONFIG
from fetch_entities import populate_feed_with_entities, get_vehicles_from_feed
from VehiclePositionFeed import VehiclePositionFeed
import util

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


# Similar to main.py
def consume_pb(VehiclePositionFeed: VehiclePositionFeed, config: dict):

    # replace with function from fetch_entities.py
    feed = populate_feed_with_entities(VehiclePositionFeed, config)
    feed_entities = get_vehicles_from_feed(feed)

    if len(feed_entities) == 0:
        logger.warning(f"Empty Protobuf file for {VehiclePositionFeed.url}")
        VehiclePositionFeed.updatetimeout(300)
        # exit out of function
        return

    if len(VehiclePositionFeed.entities) == 0:
        # check if any observations exist, if none create all new objects
        for feed_entity in feed_entities:
            entity = Entity(feed_entity)
            VehiclePositionFeed.entities.append(entity)
    else:
        current_ids = []
        # find and update entity
        for feed_entity in feed_entities:
            entity = VehiclePositionFeed.find_entity(feed_entity.id)
            if entity:
                # check if new direction and old direction are same
                # check if last updated date is equivalent to new date, to prevent duplication
                if entity.updated_at != datetime.datetime.fromtimestamp(feed_entity.vehicle.timestamp).replace(tzinfo=util.EASTERN_TIME):
                    if entity.direction_id == feed_entity.vehicle.trip.direction_id:
                        entity.update(feed_entity)
                        current_ids.append(feed_entity.id)
                    else:
                        # first remove old
                        # this checks to make sure there are at least 2 measurements
                        entity.save()
                        VehiclePositionFeed.entities.remove(entity)
                        # now create new
                        entity = Entity(feed_entity)
                        VehiclePositionFeed.entities.append(entity)
                        current_ids.append(feed_entity.id)
                else:
                    current_ids.append(feed_entity.id)
        # remove and save finished entities
        old_ids = [e.entity_id for e in VehiclePositionFeed.entities]
        ids_to_remove = [x for x in old_ids if x not in current_ids]
        for id in ids_to_remove:
            # move logic onto object
            entity = VehiclePositionFeed.find_entity(id)
            if entity:
                # call save method
                # TODO: update to save to data path
                entity.save()
                # entity.save(self.file_path)
                logger.debug(f"Saving entity {entity.entity_id}")
                # remove from list
                VehiclePositionFeed.entities.remove(entity)
