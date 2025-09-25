import requests
from google.transit import gtfs_realtime_pb2
from google.protobuf.message import DecodeError
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from ddtrace import tracer
from config import CONFIG


logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


# Config should contain headers, params, and verify=false where applicable
def populate_feed_with_entities(VehiclePositionFeed: VehiclePositionFeed, config):
    feed = None
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        # TODO: add From and User Agent Headers
        # headers = {
        #     'User-Agent': 'Your App Name/1.0',
        #     'From': 'your_email@example.com'
        # }

        response = requests.get(VehiclePositionFeed.url, **config)

        feed.ParseFromString(response.content)
    except DecodeError:
        logger.warning(f"protobuf decode error for {VehiclePositionFeed.url}")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout for {VehiclePositionFeed.url}")
        # Maybe set up for a retry, or continue in a retry loop
    except requests.exceptions.TooManyRedirects:
        logger.warning(f"Too Many Redirects for {VehiclePositionFeed.url}")
    except requests.exceptions.SSLError:
        logger.warning(f"SSL Error for {VehiclePositionFeed. url}")
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        raise SystemExit(e)
    except Exception:
        # TODO: update to be more fine-grained in future
        VehiclePositionFeed.updatetimeout(300)
        # logger.exception(e)
    # Returns list of feed entities
    return feed


def get_vehicles_from_feed(feed) -> list[any]:
    vehicles = None
    try:
        if feed:
            # TODO: check if this is the best way to filter out messages
            vehicles = [e for e in feed.entity if e.HasField("vehicle")]
    except Exception as e:
        logger.info(f"message does not have vehicle field {e}")
    if vehicles:
        return vehicles
