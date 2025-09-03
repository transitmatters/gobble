import time
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from config import CONFIG
from consume_pb import consume_pb


logger = set_up_logging(__name__)

if __name__ == "__main__":
    # rt_feed = CONFIG["rt_feeds"]
    rt_feeds = [
        {
            "feed_url": "https://bustracker.pvta.com/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
            "agency": "Pioneer Valley Transit Authority",
            "static": "http://www.pvta.com/g_trans/google_transit.zip",
            "config": {},
        },
        {
            "feed_url": "https://meva.syncromatics.com/gtfs-rt/vehiclepositions",
            "agency": "Merrimack Valley Regional Transit Authority",
            "static": "https://data.trilliumtransit.com/gtfs/merrimackvalley-ma-us/merrimackvalley-ma-us.zip",
            "config": {},
        },
        {
            "feed_url": "https://www3.septa.org/gtfsrt/septarail-pa-us/Vehicle/rtVehiclePosition.pb",
            "agency": "SEPTA Regional Rail",
            "config": {},
        },
        {
            "feed_url": "https://www3.septa.org/gtfsrt/septa-pa-us/Vehicle/rtVehiclePosition.pb",
            "agency": "SEPTA Bus Trolley",
            "config": {},
        },
        {
            "feed_url": "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb",
            "agency": "Cleveland RTA",
            "config": {},
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
