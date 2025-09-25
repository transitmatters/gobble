import time
import requests
from VehiclePositionFeed import VehiclePositionFeed
from event import process_event
from logger import set_up_logging
from consume_pb import consume_pb
from trip_state import TripsStateManager
from ddtrace import tracer
import traceback


logger = set_up_logging(__name__)


def gtfs_rt_thread():
    trips_state = TripsStateManager()
    vehicle_postion_feed = VehiclePositionFeed(feed["feed_url"], feed["agency"], timeout=30)
    while True:
        start_at = time.time()
        client = None
        try:
            consume_pb(vehicle_postion_feed)
            process_event(client, trips_state)
        except requests.exceptions.ChunkedEncodingError:
            # Keep track of how long into connections this occurs, in case it's consistent (a timeout?)
            elapsed = time.time() - start_at
            if tracer.enabled:
                logger.exception(
                    f"ChunkedEncodingError (handled) at elapsed={elapsed}s", stack_info=True, exc_info=True
                )
        except Exception:
            if tracer.enabled:
                logger.exception("Encountered an exception in gtfs_rt_thread", stack_info=True, exc_info=True)
            else:
                traceback.print_exc()
        finally:
            time.sleep(vehicle_postion_feed.timeout)  # Just in case something is borked, to avoid hammering. It doesn't GIL!


if __name__ == "__main__":
    # rt_feed = CONFIG["rt_feeds"]
    rt_feeds = [
        {
            "config": {},
            "agency": "Denver RTD",
            "feed_url": "https://open-data.rtd-denver.com/files/gtfs-rt/rtd/VehiclePosition.pb",
        },
    ]
    VehiclePositionFeeds = []
    for feed in rt_feeds:
        x = VehiclePositionFeed(feed["feed_url"], feed["agency"], timeout=30)
        VehiclePositionFeeds.append(x)
    running = True

    while running:
        for feed in VehiclePositionFeeds:
            consume_pb(feed)
        time.sleep(30)
