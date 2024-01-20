import json
import threading
import requests
import sseclient
import logging
import traceback
from ddtrace import tracer
from typing import Set

from constants import ROUTES_BUS, ROUTES_CR, ROUTES_RAPID
from config import CONFIG
from event import process_event
from logger import set_up_logging
from trip_state import TripsStateManager
import gtfs

logging.basicConfig(level=logging.INFO, filename="gobble.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY, "Accept": "text/event-stream"}


def main():
    # Start downloading GTFS bundles immediately
    gtfs.start_watching_gtfs()

    rapid_thread = threading.Thread(
        target=client_thread,
        args=(ROUTES_RAPID,),
        name="rapid_routes",
    )

    cr_thread = threading.Thread(
        target=client_thread,
        args=(ROUTES_CR,),
        name="cr_routes",
    )

    rapid_thread.start()
    cr_thread.start()

    bus_threads: list[threading.Thread] = []
    for i in range(0, len(list(ROUTES_BUS)), 10):
        routes_bus_chunk = list(ROUTES_BUS)[i : i + 10]
        bus_thread = threading.Thread(
            target=client_thread,
            args=(set(routes_bus_chunk),),
            name=f"routes_bus_chunk{i}",
        )
        bus_threads.append(bus_thread)
        bus_thread.start()

    rapid_thread.join()
    cr_thread.join()
    for bus_thread in bus_threads:
        bus_thread.join()


def client_thread(routes_filter: Set[str]):
    url = f'https://api-v3.mbta.com/vehicles?filter[route]={",".join(routes_filter)}'
    logger.info(f"Connecting to {url}...")
    client = sseclient.SSEClient(requests.get(url, headers=HEADERS, stream=True))
    trips_state = TripsStateManager()
    process_events(client, trips_state)


def process_events(client: sseclient.SSEClient, trips_state: TripsStateManager):
    for event in client.events():
        try:
            if event.event != "update":
                continue
            update = json.loads(event.data)
            process_event(update, trips_state)
        except Exception:
            if tracer.enabled:
                logger.exception("Encountered an exception when processing an event", stack_info=True, exc_info=True)
            else:
                traceback.print_exc()
            continue


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    main()
else:
    logger = set_up_logging(__name__)
