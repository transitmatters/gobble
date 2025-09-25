from Entity import Entity
import datetime
from logger import set_up_logging
from ddtrace import tracer
from config import CONFIG
from fetch_entities import populate_feed_with_entities, get_vehicles_from_feed
from VehiclePositionFeed import VehiclePositionFeed
import util
from event import process_event

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


# Similar to main.py
def consume_pb(VehiclePositionFeed: VehiclePositionFeed, config: dict):

    # replace with function from fetch_entities.py
    feed = populate_feed_with_entities(VehiclePositionFeed, config)
    feed_entities = get_vehicles_from_feed(feed)
    if feed_entities:
        if len(feed_entities) == 0:
            logger.warning(f"Empty Protobuf file for {VehiclePositionFeed.url}")
            VehiclePositionFeed.updatetimeout(300)
            # exit out of function
            return

        if len(VehiclePositionFeed.entities) == 0:
            # check if any observations exist, if none create all new objects
            for feed_entity in feed_entities:
                entity = Entity(feed_entity, VehiclePositionFeed.agency)
                VehiclePositionFeed.entities.append(entity)
                update = entity.to_mbta_json()
                yield update
                # entity.save()
        else:
            # find and update entity
            for feed_entity in feed_entities:
                # Match GTFS Feed Entity to our known last entity
                entity = VehiclePositionFeed.find_entity(feed_entity.id)
                if entity:
                    timestamp = feed_entity.vehicle.timestamp
                    if timestamp:
                        # check if last updated date is equivalent to new date, to prevent duplication
                        if entity.last_seen != timestamp:
                            entity.update(feed_entity)
                            update = entity.to_mbta_json()
                            yield update
                            # entity.save()
                        else:
                            continue
                    else:
                        continue
