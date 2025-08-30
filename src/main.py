import os
import sys
import time
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from config import CONFIG
from consume_pb import consume_pb


logger = set_up_logging(__name__)

if __name__ == "__main__":
    # rt_feeds = CONFIG["rt_feeds"]
    rt_feeds = [{"feed_url": "https://cdn.mbta.com/realtime/VehiclePositions.pb", "agency": "MBTA", "config": {}}]
    for feed in rt_feeds:
        x = VehiclePositionFeed(feed["feed_url"], feed["agency"], timeout=30)
        running = True
        while running:
            consume_pb(x, feed["config"])
            time.sleep(x.timeout)
