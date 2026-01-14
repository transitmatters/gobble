import json
import threading
import requests
import sseclient
import time
import logging
import traceback
import queue
from ddtrace import tracer
from typing import Set

from constants import ROUTES_BUS, ROUTES_CR, ROUTES_RAPID
from config import CONFIG
from event import process_event
from logger import set_up_logging
from trip_state import TripsStateManager
import gtfs
import gtfs_rt_client


logging.basicConfig(level=logging.INFO, filename="gobble.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

# Determine which mode to use: SSE (default) or GTFS-RT
USE_GTFS_RT = CONFIG.get("use_gtfs_rt", False)

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {"X-API-KEY": API_KEY, "Accept": "text/event-stream"}


class SharedGtfsRtFetcher:
    """Single GTFS-RT fetcher that broadcasts to multiple consumers."""

    def __init__(self, client: gtfs_rt_client.GtfsRtClient):
        self.client = client
        self.subscribers: list[queue.Queue] = []
        self.lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        """Subscribe to receive events. Returns a queue for this subscriber."""
        q: queue.Queue = queue.Queue(maxsize=1000)  # Prevent memory issues
        with self.lock:
            self.subscribers.append(q)
        return q

    def fetch_and_broadcast(self, all_routes: Set[str]):
        """Continuously fetch and broadcast events to all subscribers."""
        logger.info(f"Starting shared GTFS-RT fetcher for {len(all_routes)} routes")
        for event in self.client.poll_events(all_routes):
            with self.lock:
                # Broadcast to all subscribers
                for q in self.subscribers:
                    try:
                        q.put_nowait(event)
                    except queue.Full:
                        logger.warning("Subscriber queue full, dropping event")


def main():
    # Start downloading GTFS bundles immediately
    gtfs.start_watching_gtfs()

    if USE_GTFS_RT:
        # GTFS-RT mode: Use single shared fetcher
        all_routes = ROUTES_RAPID | ROUTES_CR | ROUTES_BUS
        client = gtfs_rt_client.create_gtfs_rt_client(CONFIG)
        shared_fetcher = SharedGtfsRtFetcher(client)

        # Start single fetcher thread
        fetcher_thread = threading.Thread(
            target=shared_fetcher.fetch_and_broadcast,
            args=(all_routes,),
            name="gtfs_rt_fetcher",
            daemon=True,
        )
        fetcher_thread.start()

        # Create worker threads that consume from shared feed
        rapid_thread = threading.Thread(
            target=client_thread_gtfs_rt_shared,
            args=(ROUTES_RAPID, TripsStateManager(), shared_fetcher.subscribe()),
            name="rapid_routes",
        )

        cr_thread = threading.Thread(
            target=client_thread_gtfs_rt_shared,
            args=(ROUTES_CR, TripsStateManager(), shared_fetcher.subscribe()),
            name="cr_routes",
        )

        rapid_thread.start()
        cr_thread.start()

        bus_threads: list[threading.Thread] = []
        for i in range(0, len(list(ROUTES_BUS)), 10):
            routes_bus_chunk = list(ROUTES_BUS)[i : i + 10]
            bus_thread = threading.Thread(
                target=client_thread_gtfs_rt_shared,
                args=(
                    set(routes_bus_chunk),
                    TripsStateManager(),
                    shared_fetcher.subscribe(),
                ),
                name=f"routes_bus_chunk{i}",
            )
            bus_threads.append(bus_thread)
            bus_thread.start()

        rapid_thread.join()
        cr_thread.join()
        for bus_thread in bus_threads:
            bus_thread.join()
    else:
        # SSE mode: Use existing multi-threaded approach
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


def connect(routes: Set[str]) -> requests.Response:
    url = f"https://api-v3.mbta.com/vehicles?filter[route]={','.join(routes)}"
    logger.info(f"Connecting to {url}...")
    return requests.get(url, headers=HEADERS, stream=True)


def client_thread(routes: Set[str]):
    trips_state = TripsStateManager()

    if USE_GTFS_RT:
        # GTFS-RT mode
        logger.info(f"Starting GTFS-RT client thread for routes: {routes}")
        client_thread_gtfs_rt(routes, trips_state)
    else:
        # SSE mode (default)
        logger.info(f"Starting SSE client thread for routes: {routes}")
        client_thread_sse(routes, trips_state)


def client_thread_sse(routes: Set[str], trips_state: TripsStateManager):
    """Client thread using MBTA SSE API."""
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
                    f"ChunkedEncodingError (handled) at elapsed={elapsed}s",
                    stack_info=True,
                    exc_info=True,
                )
        except Exception:
            if tracer.enabled:
                logger.exception(
                    "Encountered an exception in client_thread",
                    stack_info=True,
                    exc_info=True,
                )
            else:
                traceback.print_exc()
        finally:
            if client is not None:
                client.close()
            time.sleep(0.5)  # Just in case something is borked, to avoid hammering. It doesn't GIL!


def client_thread_gtfs_rt(routes: Set[str], trips_state: TripsStateManager):
    """Client thread using GTFS-RT polling."""
    client = None
    try:
        client = gtfs_rt_client.create_gtfs_rt_client(CONFIG)

        # Continuously poll and process events
        for event in client.poll_events(routes):
            try:
                process_event(event, trips_state)
            except Exception:
                if tracer.enabled:
                    logger.exception(
                        "Encountered an exception when processing GTFS-RT event",
                        stack_info=True,
                        exc_info=True,
                    )
                else:
                    traceback.print_exc()
                continue

    except Exception:
        if tracer.enabled:
            logger.exception(
                "Encountered an exception in GTFS-RT client_thread",
                stack_info=True,
                exc_info=True,
            )
        else:
            traceback.print_exc()
    finally:
        if client is not None:
            client.close()


def client_thread_gtfs_rt_shared(routes: Set[str], trips_state: TripsStateManager, event_queue: queue.Queue):
    """Client thread consuming from shared GTFS-RT feed."""
    logger.info(f"Starting GTFS-RT consumer thread for {len(routes)} routes")
    try:
        while True:
            event = event_queue.get()  # Blocking wait for events

            # Filter for routes this thread cares about
            route_id = event["relationships"]["route"]["data"]["id"]
            if route_id not in routes:
                continue

            try:
                process_event(event, trips_state)
            except Exception:
                if tracer.enabled:
                    logger.exception(
                        "Encountered an exception when processing GTFS-RT event",
                        stack_info=True,
                        exc_info=True,
                    )
                else:
                    traceback.print_exc()
    except Exception:
        if tracer.enabled:
            logger.exception(
                "Encountered an exception in GTFS-RT client_thread",
                stack_info=True,
                exc_info=True,
            )
        else:
            traceback.print_exc()


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
                logger.exception(
                    "Encountered an exception when processing an event",
                    stack_info=True,
                    exc_info=True,
                )
            else:
                traceback.print_exc()
            continue


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    main()
else:
    logger = set_up_logging(__name__)
