from datetime import datetime
import json
from typing import Dict
import requests
import sseclient
import logging
from ddtrace import tracer

from constants import ROUTES_BUS, ROUTES_CR
from config import CONFIG
from event import process_event
import gtfs
import disk
import util

logging.basicConfig(level=logging.INFO)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY, "Accept": "text/event-stream"}
URL = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(ROUTES_CR.union(ROUTES_BUS))}'


def main():
    current_stop_state: Dict = disk.read_state()

    # Download the gtfs bundle before we proceed so we don't have to wait
    logger.info("Downloading GTFS bundle if necessary...")
    gtfs_service_date = util.service_date(datetime.now(util.EASTERN_TIME))
    scheduled_trips, scheduled_stop_times, stops = gtfs.read_gtfs(gtfs_service_date)

    logger.info(f"Connecting to {URL}...")
    client = sseclient.SSEClient(requests.get(URL, headers=HEADERS, stream=True))

    for event in client.events():
        if event.event != "update":
            continue

        update = json.loads(event.data)
        process_event(update, current_stop_state, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops)


if __name__ == "__main__":
    logger = logging.getLogger(__file__)
    main()
else:
    logger = logging.getLogger(__name__)
