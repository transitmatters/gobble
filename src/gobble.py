from datetime import datetime
import json
from typing import Dict
import requests
import sseclient
import logging
from ddtrace import tracer
import urllib3

from constants import ALL_ROUTES
from config import CONFIG
from event import process_event
from logger import set_up_logging
import gtfs
import disk
import util

logging.basicConfig(level=logging.INFO, filename="gobble.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY, "Accept": "text/event-stream"}
URL = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(ALL_ROUTES)}'


def main():
    current_stop_state: Dict = disk.read_state()

    # Download the gtfs bundle before we proceed so we don't have to wait
    logger.info("Downloading GTFS bundle if necessary...")
    gtfs_service_date = util.service_date(datetime.now(util.EASTERN_TIME))
    scheduled_trips, scheduled_stop_times, stops = gtfs.read_gtfs(gtfs_service_date)

    logger.info(f"Connecting to {URL}...")
    client = sseclient.SSEClient(requests.get(URL, headers=HEADERS, stream=True))

    for event in client.events():
        try:
            if event.event != "update":
                continue

            update = json.loads(event.data)
            process_event(update, current_stop_state, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops)
        except urllib3.exceptions.InvalidChunkLength:
            logger.exception("Encountered invalid chunk length issue, skipping event", stack_info=True, exc_info=True)
            continue


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    main()
else:
    logger = set_up_logging(__name__)
