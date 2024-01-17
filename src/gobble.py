from datetime import date, datetime
import json
import threading
from typing import Dict
import pandas as pd
import requests
import sseclient
import logging
from ddtrace import tracer

from constants import ROUTES_BUS, ROUTES_CR, ROUTES_RAPID
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


def main():
    # Download the gtfs bundle before we proceed so we don't have to wait
    logger.info("Downloading GTFS bundle if necessary...")
    gtfs_service_date = util.service_date(datetime.now(util.EASTERN_TIME))
    scheduled_trips, scheduled_stop_times, stops = gtfs.read_gtfs(gtfs_service_date)

    rapid_url = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(ROUTES_RAPID)}'
    rapid_thread = threading.Thread(
        target=client_thread,
        args=(rapid_url, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops),
        name="rapid_routes",
    )

    cr_url = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(ROUTES_CR)}'
    cr_thread = threading.Thread(
        target=client_thread,
        args=(cr_url, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops),
        name="cr_routes",
    )

    rapid_thread.start()
    cr_thread.start()

    bus_threads: list[threading.Thread] = []
    for i in range(0, len(list(ROUTES_BUS)), 10):  
        bus_routes = list(ROUTES_BUS)[i:i + 10] 
        bus_url = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(bus_routes)}'
        bus_thread = threading.Thread(
            target=client_thread,
            args=(bus_url, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops),
            name=f"bus_routes{i}",
        )
        bus_threads.append(bus_thread)
        bus_thread.start()

    rapid_thread.join()
    cr_thread.join()
    for bus_thread in bus_threads:
        bus_thread.join()


def client_thread(
    url: str,
    gtfs_service_date: date,
    scheduled_trips: pd.DataFrame,
    scheduled_stop_times: pd.DataFrame,
    stops: pd.DataFrame,
):
    logger.info(f"Connecting to {url}...")
    client = sseclient.SSEClient(requests.get(url, headers=HEADERS, stream=True))

    current_stop_state: Dict = disk.read_state()

    process_events(client, current_stop_state, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops)


def process_events(
    client: sseclient.SSEClient, current_stop_state, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops
):
    for event in client.events():
        try:
            if event.event != "update":
                continue

            update = json.loads(event.data)
            process_event(update, current_stop_state, gtfs_service_date, scheduled_trips, scheduled_stop_times, stops)
        except Exception:
            logger.exception("Encountered an exception when processing an event", stack_info=True, exc_info=True)
            continue


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    main()
else:
    logger = set_up_logging(__name__)
