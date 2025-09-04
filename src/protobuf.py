import datetime
from google.transit import gtfs_realtime_pb2 as gtfs
from google.protobuf.message import DecodeError
import requests
from logger import set_up_logging
from ddtrace import tracer
from config import CONFIG
import util
from src.gtfs_types import OccupancyStatus

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


# params should contain headers, params, and verify=false where applicable
def populate_feed_with_entities(url: str, params: dict) -> gtfs.FeedMessage:
    feed = None
    try:
        feed = gtfs.FeedMessage()
        response = requests.get(url, **params)
        # populates feed in place
        feed.ParseFromString(response.content)
    except DecodeError:
        logger.warning(f"protobuf decode error for {url}")
        return []
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout for {url}")
        # Maybe set up for a retry, or continue in a retry loop
        return []
    except requests.exceptions.TooManyRedirects:
        logger.warning(f"Too Many Redirects for {url}")
        return []
    except requests.exceptions.SSLError:
        logger.warning(f"SSL Error for {url}")
        return []
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        raise SystemExit(e)
    except Exception as e:
        # TODO: update to be more fine-grained in future
        logger.exception(e)
        return []
    # Returns list of feed entities
    return feed


def get_vehicles_from_feed(feed: gtfs.FeedMessage) -> list[gtfs.FeedEntity]:
    try:
        if feed:
            # TODO: check if this is the best way to filter out messages
            vehicles = [e for e in feed.entity if e.HasField("vehicle")]
            return vehicles
        else:
            vehicles = []
            return vehicles
    except Exception as e:
        logger.info(f"message does not have vehicle field {e}")
        vehicles = []
        return vehicles


def produce_dict_from_protobuf(url: str, config: dict):
    # replace with function from fetch_entities.py
    feed = populate_feed_with_entities(url, config)
    feed_entities = get_vehicles_from_feed(feed)
    if feed_entities:
        if len(feed_entities) == 0:
            logger.warning(f"Empty Protobuf file for {url}")
            # exit out of function
            return []
        else:
            for feed_ent in feed_entities:
                yield convert_protobuf_to_dict(feed_ent)
    else:
        return []

def convert_carriage_to_dict(carriage_details):
    label: str = carriage_details.label
    carriage_sequence: int = carriage_details.carriage_sequence
    occupancy_status: list[OccupancyStatus] = [carriage_details.occupancy_status]
    return {"label":label,"carriage_sequence":carriage_sequence,"occupancy_status":occupancy_status}



def convert_protobuf_to_dict(entity):
    carriages = [convert_carriage_to_dict(c) for c in entity.vehicle.multi_carriage_details]
    x = {
      "attributes": {
        "bearing": entity.vehicle.position.bearing,
        "carriages": [],
        "current_status": entity.vehicle.current_status,
        "current_stop_sequence": entity.vehicle.current_stop_sequence,
        "direction_id": entity.vehicle.trip.direction_id,
        "label": entity.vehicle.vehicle.label,
        "latitude": entity.vehicle.position.latitude,
        "longitude": entity.vehicle.position.longitude,
        "occupancy_status": entity.vehicle.occupancy_status,
        "revenue": "REVENUE",
        "speed": None,
        "updated_at": datetime.datetime.fromtimestamp(entity.timestamp, tz=datetime.tzinfo).isoformat() if entity.HasField("timestamp") else None
      },
      "id": entity.vehicle.vehicle.id,
      "links": {
        "self": None
      },
      "relationships": {
        "route": {
          "data": {
            "id": entity.vehicle.trip.route_id,
            "type": "route"
          }
        },
        "stop": {
          "data": {
            "id": entity.vehicle.stop_id,
            "type": "stop"
          }
        },
        "trip": {
          "data": {
            "id": entity.vehicle.trip.trip_id,
            "type": "trip"
          }
        }
      },
      "type": "vehicle"
    }
    #
    #
    #
    #         entity.id
    #         entity.vehicle.trip.schedule_relationship
    #         entity.vehicle.trip.start_date
    #         entity.vehicle.trip.start_time
    #
    #
    #         entity.vehicle.vehicle.license_plate
    #         entity.vehicle.timestamp
    #
    #         entity.vehicle.position.odometer
    #
    #
    #
    #
    #         entity.vehicle.occupancy_percentage
    #        entity.vehicle.congestion_level
    # []
    #
    # if len(VehiclePositionFeed.entities) == 0:
    #     # check if any observations exist, if none create all new objects
    #     for feed_entity in feed_entities:
    #         entity = Entity(feed_entity, VehiclePositionFeed.agency)
    #         VehiclePositionFeed.entities.append(entity)
    # else:
    #     current_ids = []
    #     # find and update entity
    #     for feed_entity in feed_entities:
    #         entity = VehiclePositionFeed.find_entity(feed_entity.id)
    #         if entity:
    #             # check if new direction and old direction are same
    #             # check if last updated date is equivalent to new date, to prevent duplication
    #             if entity.updated_at != datetime.datetime.fromtimestamp(feed_entity.vehicle.timestamp).replace(
    #                 tzinfo=util.EASTERN_TIME
    #             ):
    #                 if entity.direction_id == feed_entity.vehicle.trip.direction_id:
    #                     entity.update(feed_entity)
    #                     current_ids.append(feed_entity.id)
    #                 else:
    #                     # first remove old
    #                     # this checks to make sure there are at least 2 measurements
    #                     entity.save()
    #                     VehiclePositionFeed.entities.remove(entity)
    #                     # now create new
    #                     entity = Entity(feed_entity, VehiclePositionFeed.agency)
    #                     VehiclePositionFeed.entities.append(entity)
    #                     current_ids.append(feed_entity.id)
    #             else:
    #                 current_ids.append(feed_entity.id)
    #     # remove and save finished entities
    #     old_ids = [e.entity_id for e in VehiclePositionFeed.entities]
    #     ids_to_remove = [x for x in old_ids if x not in current_ids]
    #     for id in ids_to_remove:
    #         # move logic onto object
    #         entity = VehiclePositionFeed.find_entity(id)
    #         if entity:
    #             # call save method
    #             # TODO: update to save to data path
    #             entity.save()
    #             # entity.save(self.file_path)
    #             logger.debug(f"Saving entity {entity.entity_id}")
    #             # remove from list
    #             VehiclePositionFeed.entities.remove(entity)
