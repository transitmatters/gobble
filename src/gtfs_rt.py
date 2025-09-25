import time
import requests
from VehiclePositionFeed import VehiclePositionFeed
from event import process_event
from logger import set_up_logging
from consume_pb import consume_pb
from trip_state import TripsStateManager
from ddtrace import tracer
import traceback
import gtfs
import threading
import json
from config import CONFIG
import logging

logging.basicConfig(level=logging.INFO, filename="gobble.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]
API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY}


def gtfs_rt_thread():
    trips_state = TripsStateManager()
    vehicle_postion_feed = VehiclePositionFeed("https://cdn.mbta.com/realtime/VehiclePositions.pb", "MBTA", timeout=30)
    config = {"headers": HEADERS}
    while True:
        start_at = time.time()
        try:
            for update in consume_pb(vehicle_postion_feed, config):
                if update:
                    update_dict = json.loads(update)
                    process_event(update_dict, trips_state)
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
            time.sleep(
                vehicle_postion_feed.timeout
            )  # Just in case something is borked, to avoid hammering. It doesn't GIL!


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    gtfs.start_watching_gtfs()

    mbta_gtfs_rt_thread = threading.Thread(
        target=gtfs_rt_thread,
        args=(),
        name="gtfs_rt",
    )
    mbta_gtfs_rt_thread.start()
    mbta_gtfs_rt_thread.join()
else:
    logger = set_up_logging(__name__)
