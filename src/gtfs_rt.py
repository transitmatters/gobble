import time
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from consume_pb import consume_pb


logger = set_up_logging(__name__)

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
            consume_pb(feed, {})
        time.sleep(30)
