import os
import time
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from config import CONFIG
from utils.consume_pb import consume_pb


logger = set_up_logging(__name__)

if __name__ == "__main__":
    rt_feeds = CONFIG["rt_feeds"]
    for feed in rt_feeds:
        x = VehiclePositionFeed(feed["feed_url"], feed["agency"], f"./data/{provider}", timeout=30)
        running = True
        while running:
            consume_pb(x, feed["config"])
            time.sleep(x.timeout)
