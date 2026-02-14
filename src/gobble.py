import json
import logging
import threading
import time
import traceback
from typing import Set

import requests
import sseclient
from ddtrace import tracer

import gtfs
from config import CONFIG
from constants import ROUTES_BUS, ROUTES_CR, ROUTES_RAPID
from event import process_event
from logger import set_up_logging
from trip_state import TripsStateManager

logging.basicConfig(level=logging.INFO, filename="gobble.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY, "Accept": "text/event-stream"}


def main():
    # Start downloading GTFS bundles immediately
    gtfs.start_watching_gtfs()

    # Get enabled modes from config, default to all modes if not specified
    enabled_modes = CONFIG.get("modes", ["rapid", "cr", "bus"])

    threads: list[threading.Thread] = []

    if "rapid" in enabled_modes:
        rapid_thread = threading.Thread(
            target=client_thread,
            args=(ROUTES_RAPID,),
            name="rapid_routes",
        )
        threads.append(rapid_thread)
        rapid_thread.start()

    if "cr" in enabled_modes:
        cr_thread = threading.Thread(
            target=client_thread,
            args=(ROUTES_CR,),
            name="cr_routes",
        )
        threads.append(cr_thread)
        cr_thread.start()

    if "bus" in enabled_modes:
        for i in range(0, len(list(ROUTES_BUS)), 10):
            routes_bus_chunk = list(ROUTES_BUS)[i : i + 10]
            bus_thread = threading.Thread(
                target=client_thread,
                args=(set(routes_bus_chunk),),
                name=f"routes_bus_chunk{i}",
            )
            threads.append(bus_thread)
            bus_thread.start()

    for thread in threads:
        thread.join()


def connect(routes: Set[str]) -> requests.Response:
    url = f"https://api-v3.mbta.com/vehicles?filter[route]={','.join(routes)}"
    logger.info(f"Connecting to {url}...")
    return requests.get(url, headers=HEADERS, stream=True)


def client_thread(routes: Set[str]):
    trips_state = TripsStateManager()
    while True:
        start_at = time.time()
        client = None
        try:
            client = sseclient.SSEClient(connect(routes))  # type: ignore
            process_events(client, trips_state)
        except requests.exceptions.ChunkedEncodingError:
            # Keep track of how long into connections this occurs, in case it's consistent (a timeout?)
            elapsed = time.time() - start_at
            if tracer.enabled:
                logger.exception(
                    f"ChunkedEncodingError (handled) at elapsed={elapsed}s", stack_info=True, exc_info=True
                )
        except Exception:
            if tracer.enabled:
                logger.exception("Encountered an exception in client_thread", stack_info=True, exc_info=True)
            else:
                traceback.print_exc()
        finally:
            if client is not None:
                client.close()
            time.sleep(0.5)  # Just in case something is borked, to avoid hammering. It doesn't GIL!


def process_events(client: sseclient.SSEClient, trips_state: TripsStateManager):
    for event in client.events():
        try:
            if event.event == "update":
                update = json.loads(event.data)
                process_event(update, trips_state)
            if event.event == "reset":
                updates = json.loads(event.data)
                for update in updates:
                    process_event(update, trips_state)
            if event.event == "add":
                update = json.loads(event.data)
                process_event(update, trips_state)
            else:
                continue
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
