"""GTFS archive management and schedule data processing.

This module handles downloading, caching, and querying GTFS (General Transit
Feed Specification) schedule data from the MBTA. It provides functions to:
- Download and cache GTFS archives based on service date
- Query trips and stop times for specific routes
- Calculate scheduled headways and travel times
- Match real-time events to scheduled values

The module maintains a thread-safe global GTFS archive that is automatically
updated when the service date changes.

Attributes:
    MAIN_DIR: Directory for storing downloaded GTFS archives.
    GTFS_ARCHIVES_PREFIX: Base URL for MBTA GTFS archive downloads.
    RTE_DIR_STOP: Common column names for route/direction/stop grouping.
    current_gtfs_archive: Global cached GtfsArchive for the current service date.
"""

import datetime
import pandas as pd
import pathlib
import shutil
import urllib.request
import time
from urllib.parse import urljoin
from dataclasses import dataclass
from ddtrace import tracer
from threading import Lock, Thread
from typing import List, Dict, Optional, Set

from config import CONFIG
from constants import ALL_ROUTES
from logger import set_up_logging
from util import EASTERN_TIME

import util

logger = set_up_logging(__name__)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]


MAIN_DIR = pathlib.Path("./data/gtfs_archives/")
MAIN_DIR.mkdir(parents=True, exist_ok=True)

GTFS_ARCHIVES_PREFIX = "https://cdn.mbta.com/archive/"
GTFS_ARCHIVES_FILENAME = "archived_feeds.txt"

# defining these columns in particular becasue we use them everywhere
RTE_DIR_STOP = ["route_id", "direction_id", "stop_id"]

# only fetch required columns from gtfs csv's to reduce memory usage
STOP_TIMES_COLS = ["stop_id", "trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]


def _group_df_by_column(df: pd.DataFrame, column_name: str) -> Dict[str, pd.DataFrame]:
    """Group a DataFrame by a column and return a dictionary of sub-DataFrames.

    Args:
        df: The DataFrame to group.
        column_name: The column to group by.

    Returns:
        Dictionary mapping column values to their corresponding DataFrames.
    """
    return {key: df_group for key, df_group in df.groupby(column_name)}


def _get_empty_df_with_same_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Create an empty DataFrame with the same columns as the input.

    Args:
        df: The DataFrame whose column structure to copy.

    Returns:
        An empty DataFrame with the same columns as the input.
    """
    empty_df = df.copy(deep=False)
    empty_df.drop(empty_df.index, inplace=True)
    return empty_df


@dataclass
class GtfsArchive:
    """Container for GTFS schedule data for a specific service date.

    Holds pre-filtered and indexed GTFS data for efficient lookup during
    event processing. Data is organized by route for fast access.

    Attributes:
        trips: DataFrame of all trips for the service date.
        stop_times: DataFrame of all stop times for all trips.
        stops: DataFrame of all stop definitions.
        service_date: The date this archive represents.
    """

    # All trips on all routes
    trips: pd.DataFrame
    # All stop times on all trips
    stop_times: pd.DataFrame
    # All stops
    stops: pd.DataFrame
    # The current service date
    service_date: datetime.date

    def __post_init__(self):
        self._trips_empty = _get_empty_df_with_same_columns(self.trips)
        self._stop_times_empty = _get_empty_df_with_same_columns(self.stop_times)
        self._trips_by_route_id = _group_df_by_column(self.trips, "route_id")
        self._stop_times_by_route_id = {}
        for route_id in self._trips_by_route_id.keys():
            trip_ids_for_route = self._trips_by_route_id[route_id].trip_id
            self._stop_times_by_route_id[route_id] = self.stop_times[self.stop_times.trip_id.isin(trip_ids_for_route)]

    def stop_times_by_route_id(self, route_id: str) -> pd.DataFrame:
        """Get stop times for a specific route.

        Args:
            route_id: The route identifier to look up.

        Returns:
            DataFrame of stop times for the route, or an empty DataFrame
            if the route is not found.
        """
        return self._stop_times_by_route_id.get(route_id, self._stop_times_empty)

    def trips_by_route_id(self, route_id: str) -> pd.DataFrame:
        """Get trips for a specific route.

        Args:
            route_id: The route identifier to look up.

        Returns:
            DataFrame of trips for the route, or an empty DataFrame
            if the route is not found.
        """
        return self._trips_by_route_id.get(route_id, self._trips_empty)


@tracer.wrap()
def _download_gtfs_archives_list() -> pd.DataFrame:
    """Download the list of available GTFS archives from MBTA.

    Fetches the archived_feeds.txt file from the MBTA CDN which contains
    metadata about all available GTFS archives including date ranges and
    download URLs.

    Returns:
        DataFrame containing archive metadata with columns including
        feed_start_date, feed_end_date, and archive_url.

    Raises:
        PermissionError: If unable to write the archives file to disk
            (continues with in-memory data).
    """
    archives_df = None
    try:
        archives_df = pd.read_csv(urljoin(GTFS_ARCHIVES_PREFIX, GTFS_ARCHIVES_FILENAME))
        archives_df.to_csv(MAIN_DIR / GTFS_ARCHIVES_FILENAME)
        return archives_df
    except (PermissionError, OSError, IOError) as e:
        logger.error(f"Failed to write GTFS archives file due to permission error: {e}")
        logger.warning("Continuing with downloaded archives data without saving to disk")
        return archives_df


def to_dateint(date: datetime.date) -> int:
    """Convert a date to an integer in YYYYMMDD format.

    Args:
        date: A date object to convert.

    Returns:
        Integer representation of the date (e.g., 20220615 for June 15, 2022).
    """
    return int(str(date).replace("-", ""))


def _find_most_recent_gtfs_archive() -> Optional[pathlib.Path]:
    """Find the most recently downloaded GTFS archive on disk.

    Scans the GTFS archives directory for existing downloads and returns
    the path to the most recent one based on directory name (date-based).

    Returns:
        Path to the most recent accessible archive directory, or None if
        no archives are found or accessible.
    """
    try:
        # Get all directories in the GTFS archives folder
        archive_dirs = [d for d in MAIN_DIR.iterdir() if d.is_dir() and d.name != "archived_feeds.txt"]

        if not archive_dirs:
            return None

        # Sort by directory name (which should be date-based) in descending order
        archive_dirs.sort(key=lambda x: x.name, reverse=True)

        # Return the first accessible directory
        for archive_dir in archive_dirs:
            try:
                # Test if we can read the directory and its contents
                list(archive_dir.iterdir())
                return archive_dir
            except (PermissionError, OSError, IOError):
                logger.warning(f"Cannot access GTFS archive directory: {archive_dir}")
                continue

        return None
    except (PermissionError, OSError, IOError) as e:
        logger.error(f"Failed to scan GTFS archives directory: {e}")
        return None


@tracer.wrap()
def get_gtfs_archive(dateint: int) -> pathlib.Path:
    """Get or download the GTFS archive for a specific date.

    Looks up which GTFS feed covers the specified date and returns the
    path to that archive, downloading it if not already cached locally.
    Includes logic to periodically check for newer archives based on
    the configured refresh interval.

    Args:
        dateint: Date as an integer in YYYYMMDD format.

    Returns:
        Path to the GTFS archive directory.

    Raises:
        ValueError: If no GTFS archive covers the specified date.
        RuntimeError: If no archives are accessible and download fails.
    """
    matches = pd.DataFrame()
    should_refetch = False

    try:
        if (MAIN_DIR / GTFS_ARCHIVES_FILENAME).exists():
            archives_df = pd.read_csv(MAIN_DIR / GTFS_ARCHIVES_FILENAME)
            matches = archives_df[(archives_df.feed_start_date <= dateint) & (archives_df.feed_end_date >= dateint)]

            # Check if we should refetch based on time since feed start date
            if len(matches) > 0:
                current_feed = matches.iloc[0]
                feed_start_date = datetime.datetime.strptime(str(current_feed.feed_start_date), "%Y%m%d").date()
                days_since_start = (datetime.date.today() - feed_start_date).days
                refresh_interval = CONFIG["gtfs"]["refresh_interval_days"]

                if days_since_start >= refresh_interval:
                    logger.info(
                        f"Feed is {days_since_start} days old (>= {refresh_interval} days). Checking for newer archives."
                    )
                    should_refetch = True
        else:
            should_refetch = True

        # if there are no matches, we havent downloaded the url list yet, or we should refetch,
        # fetch (or refetch) the archives and seek matches
        if len(matches) == 0 or should_refetch:
            if len(matches) == 0:
                logger.info("No matches found in existing GTFS archives. Fetching latest archives.")
            else:
                logger.info("Fetching latest archives to check for updates.")
            archives_df = _download_gtfs_archives_list()
            matches = archives_df[(archives_df.feed_start_date <= dateint) & (archives_df.feed_end_date >= dateint)]

        if len(matches) == 0:
            raise ValueError(f"No GTFS archive found for date {dateint}")

        archive_url = matches.iloc[0].archive_url
        archive_name = pathlib.Path(archive_url).stem

        if (MAIN_DIR / archive_name).exists():
            logger.info(f"GTFS archive for {dateint} already downloaded: {archive_name}")
            return MAIN_DIR / archive_name

        # else we have to download it
        logger.info(f"Downloading GTFS archive for {dateint}: {archive_url}")
        zipfile, _ = urllib.request.urlretrieve(archive_url)
        shutil.unpack_archive(zipfile, extract_dir=(MAIN_DIR / archive_name), format="zip")
        # remove temporary zipfile
        urllib.request.urlcleanup()

        return MAIN_DIR / archive_name

    except (PermissionError, OSError, IOError) as e:
        logger.error(f"Permission error accessing GTFS archives file: {e}")
        logger.warning("Falling back to most recent available GTFS archive")

        # Try to find the most recent available archive
        fallback_archive = _find_most_recent_gtfs_archive()
        if fallback_archive:
            logger.info(f"Using fallback GTFS archive: {fallback_archive}")
            return fallback_archive
        else:
            logger.error("No accessible GTFS archives found. Cannot continue.")
            raise RuntimeError(
                "No accessible GTFS archives available and cannot download new ones due to permission errors"
            )

    except Exception as e:
        logger.error(f"Unexpected error in get_gtfs_archive: {e}")
        logger.warning("Attempting to use most recent available GTFS archive as fallback")

        # Try to find the most recent available archive as a last resort
        fallback_archive = _find_most_recent_gtfs_archive()
        if fallback_archive:
            logger.info(f"Using fallback GTFS archive: {fallback_archive}")
            return fallback_archive
        else:
            logger.error("No accessible GTFS archives found. Cannot continue.")
            raise


@tracer.wrap()
def get_services(date: datetime.date, archive_dir: pathlib.Path) -> List[str]:
    """Determine which service IDs were active on a given date.

    Reads calendar.txt and calendar_dates.txt from the GTFS archive to
    determine which services ran on the specified date, accounting for
    the day of week and any exceptions (holidays, special events, etc.).

    Args:
        date: The date to look up services for.
        archive_dir: Path to the GTFS archive directory.

    Returns:
        List of active service IDs for the date.
    """
    dateint = to_dateint(date)
    day_of_week = date.strftime("%A").lower()

    cal = pd.read_csv(archive_dir / "calendar.txt")
    current_services = cal[(cal.start_date <= dateint) & (cal.end_date >= dateint)]
    services = current_services[current_services[day_of_week] == 1].service_id.tolist()

    exceptions = pd.read_csv(archive_dir / "calendar_dates.txt")
    exceptions = exceptions[exceptions.date == dateint]
    additions = exceptions[exceptions.exception_type == 1].service_id.tolist()
    subtractions = exceptions[exceptions.exception_type == 2].service_id.tolist()

    services = (set(services) - set(subtractions)) | set(additions)
    return list(services)


@tracer.wrap()
def read_gtfs(date: datetime.date, routes_filter: Optional[Set[str]] = None) -> GtfsArchive:
    """Load GTFS data for a specific date into a GtfsArchive.

    Downloads the appropriate GTFS archive if needed, determines which
    services ran on the date, and loads the relevant trips and stop times
    into a GtfsArchive object.

    Args:
        date: The service date to load GTFS data for.
        routes_filter: Optional set of route IDs to filter by. If provided,
            only trips on these routes are included.

    Returns:
        GtfsArchive containing trips, stop_times, and stops DataFrames
        for the specified date and routes.
    """
    dateint = to_dateint(date)
    logger.info(f"Reading GTFS archive for {date}")

    archive_dir = get_gtfs_archive(dateint)
    services = get_services(date, archive_dir)

    # specify dtypes to avoid warnings
    trips = pd.read_csv(archive_dir / "trips.txt", dtype={"trip_short_name": str, "block_id": str})
    trips = trips[trips.service_id.isin(services)]
    # filter by routes
    if routes_filter:
        trips = trips[trips.route_id.isin(routes_filter)]

    stops = pd.read_csv(archive_dir / "stops.txt")

    stop_times = pd.read_csv(
        archive_dir / "stop_times.txt", dtype={"trip_id": str, "stop_id": str}, usecols=STOP_TIMES_COLS
    )
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    stop_times.arrival_time = pd.to_timedelta(stop_times.arrival_time)
    stop_times.departure_time = pd.to_timedelta(stop_times.departure_time)

    return GtfsArchive(trips=trips, stop_times=stop_times, stops=stops, service_date=date)


@tracer.wrap()
def batch_add_gtfs_headways(events_df: pd.DataFrame, trips: pd.DataFrame, stop_times: pd.DataFrame) -> pd.DataFrame:
    """Add scheduled headway and travel time data to multiple events.

    Batch version of add_gtfs_headways that processes multiple events
    grouped by service date. Matches each event to the nearest scheduled
    stop time and calculates headway and travel time from schedule.

    Args:
        events_df: DataFrame containing multiple events with route_id,
            direction_id, stop_id, trip_id, event_time, and service_date.
        trips: DataFrame of GTFS trips for the relevant routes.
        stop_times: DataFrame of GTFS stop times for the relevant trips.

    Returns:
        DataFrame with original events augmented with scheduled_headway
        and scheduled_tt columns.
    """
    results = []

    # we have to do this day-by-day because gtfs changes so often
    for service_date, days_events in events_df.groupby("service_date"):
        # filter out the trips of interest
        relevant_trips = trips[trips.route_id.isin(days_events.route_id)]

        # take only the stops from those trips (adding route and dir info)
        trip_info = relevant_trips[["trip_id", "route_id", "direction_id"]]
        gtfs_stops = stop_times.merge(trip_info, on="trip_id", how="right")

        # calculate gtfs headways
        gtfs_stops = gtfs_stops.sort_values(by="arrival_time")
        headways = gtfs_stops.groupby(RTE_DIR_STOP).arrival_time.diff()
        # the first stop of a trip doesnt technically have a real scheduled headway, so we set to empty string
        headways = headways.fillna("")
        gtfs_stops["scheduled_headway"] = headways.dt.seconds

        # calculate gtfs traveltimes
        trip_start_times = gtfs_stops.groupby("trip_id").arrival_time.transform("min")
        gtfs_stops["scheduled_tt"] = (gtfs_stops.arrival_time - trip_start_times).dt.seconds

        # assign each actual timepoint a scheduled headway
        # merge_asof 'backward' matches the previous scheduled value of 'arrival_time'
        days_events["arrival_time"] = days_events.event_time - pd.Timestamp(service_date).tz_localize(EASTERN_TIME)
        augmented_events = pd.merge_asof(
            days_events.sort_values(by="arrival_time"),
            gtfs_stops[RTE_DIR_STOP + ["arrival_time", "scheduled_headway"]],
            on="arrival_time",
            direction="backward",
            by=RTE_DIR_STOP,
        )

        # assign each actual trip a scheduled trip_id, based on when it started the route
        route_starts = days_events.loc[days_events.groupby("trip_id").event_time.idxmin()]
        route_starts = route_starts[RTE_DIR_STOP + ["trip_id", "arrival_time"]]

        trip_id_map = pd.merge_asof(
            route_starts.sort_values(by="arrival_time"),
            gtfs_stops[RTE_DIR_STOP + ["arrival_time", "trip_id"]],
            on="arrival_time",
            direction="nearest",
            by=RTE_DIR_STOP,
            suffixes=["", "_scheduled"],
        )
        trip_id_map = trip_id_map.set_index("trip_id").trip_id_scheduled

        # use the scheduled trip matching to get the scheduled traveltime
        augmented_events["scheduled_trip_id"] = augmented_events.trip_id.map(trip_id_map)
        augmented_events = pd.merge(
            augmented_events,
            gtfs_stops[RTE_DIR_STOP + ["trip_id", "scheduled_tt"]],
            how="left",
            left_on=RTE_DIR_STOP + ["scheduled_trip_id"],
            right_on=RTE_DIR_STOP + ["trip_id"],
            suffixes=["", "_gtfs"],
        )

        # finally, put all the days together
        results.append(augmented_events)

    return pd.concat(results)


@tracer.wrap()
def add_gtfs_headways(event_df: pd.DataFrame, all_trips: pd.DataFrame, all_stops: pd.DataFrame) -> pd.DataFrame:
    """Add scheduled headway and travel time data to a single event.

    Matches the event to the nearest scheduled stop time using pandas
    merge_asof for time-based matching. Calculates the scheduled headway
    (time since previous scheduled arrival at this stop) and scheduled
    travel time (time since trip start).

    Args:
        event_df: DataFrame containing a single event row with route_id,
            direction_id, stop_id, trip_id, event_time, and service_date.
        all_trips: DataFrame of GTFS trips for the route.
        all_stops: DataFrame of GTFS stop times for the route's trips.

    Returns:
        DataFrame with the event augmented with scheduled_headway and
        scheduled_tt columns.

    Note:
        Event times are temporarily converted to pandas Timestamps for
        merge operations. All times must be in US/Eastern timezone.
        If event_df contains multiple rows, delegates to batch_add_gtfs_headways.
    """
    # TODO: I think we need to worry about 114/116/117 headways?
    if len(event_df) > 1:
        return batch_add_gtfs_headways(event_df, all_trips, all_stops)

    service_date = event_df.service_date.iloc[0]
    route_id = event_df.route_id.iloc[0]
    # filter out the trips of interest
    relevant_trips = all_trips[all_trips.route_id == route_id]

    # take only the stops from those trips (adding route and dir info)
    trip_info = relevant_trips[["trip_id", "route_id", "direction_id"]]
    gtfs_stops = all_stops.merge(trip_info, on="trip_id", how="right")

    # calculate gtfs headways
    gtfs_stops = gtfs_stops.sort_values(by="arrival_time")
    headways = gtfs_stops.groupby(RTE_DIR_STOP).arrival_time.diff()
    # the first stop of a trip doesnt technically have a real scheduled headway, so we set to empty string
    headways = headways.fillna("")
    gtfs_stops["scheduled_headway"] = headways.dt.seconds

    # calculate gtfs traveltimes
    trip_start_times = gtfs_stops.groupby("trip_id").arrival_time.transform("min")
    gtfs_stops["scheduled_tt"] = (gtfs_stops.arrival_time - trip_start_times).dt.seconds

    # assign each actual timepoint a scheduled headway
    # merge_asof 'backward' matches the previous scheduled value of 'arrival_time'
    event_df["arrival_time"] = event_df.event_time - pd.Timestamp(service_date).tz_localize(EASTERN_TIME)
    augmented_event = pd.merge_asof(
        event_df,
        gtfs_stops[RTE_DIR_STOP + ["arrival_time", "scheduled_headway"]],
        on="arrival_time",
        direction="backward",
        by=RTE_DIR_STOP,
    )

    # assign each actual trip a scheduled trip_id, based on when it started the route
    route_starts = event_df[RTE_DIR_STOP + ["trip_id", "arrival_time"]]

    trip_id_map = pd.merge_asof(
        route_starts,
        gtfs_stops[RTE_DIR_STOP + ["arrival_time", "trip_id"]],
        on="arrival_time",
        direction="nearest",
        by=RTE_DIR_STOP,
        suffixes=["", "_scheduled"],
    )
    trip_id_map = trip_id_map.set_index("trip_id").trip_id_scheduled

    # use the scheduled trip matching to get the scheduled traveltime
    augmented_event["scheduled_trip_id"] = augmented_event.trip_id.map(trip_id_map)
    augmented_event = pd.merge(
        augmented_event,
        gtfs_stops[RTE_DIR_STOP + ["trip_id", "scheduled_tt"]],
        how="left",
        left_on=RTE_DIR_STOP + ["scheduled_trip_id"],
        right_on=RTE_DIR_STOP + ["trip_id"],
        suffixes=["", "_gtfs"],
    )

    return augmented_event


current_gtfs_archive = None
write_gtfs_archive_lock = Lock()


def update_current_gtfs_archive_if_necessary():
    """Update the global GTFS archive if the service date has changed.

    Thread-safe function that checks if the cached GTFS archive is still
    valid for the current service date and downloads a new one if needed.
    Uses a lock to prevent concurrent updates.
    """
    global current_gtfs_archive
    global write_gtfs_archive_lock
    with write_gtfs_archive_lock:
        gtfs_service_date = util.service_date(datetime.datetime.now(util.EASTERN_TIME))
        needs_update = current_gtfs_archive is None or current_gtfs_archive.service_date != gtfs_service_date
        if needs_update:
            if current_gtfs_archive is None:
                logger.info(f"Downloading GTFS archive for {gtfs_service_date}")
            else:
                logger.info(f"Updating GTFS archive from {current_gtfs_archive.service_date} to {gtfs_service_date}")
            current_gtfs_archive = read_gtfs(gtfs_service_date, routes_filter=ALL_ROUTES)


def get_current_gtfs_archive() -> GtfsArchive:
    """Get the current GTFS archive, loading it if necessary.

    Returns the cached GTFS archive for the current service date. If no
    archive is cached, triggers an update to load one.

    Returns:
        The GtfsArchive for the current service date.
    """
    global current_gtfs_archive
    if current_gtfs_archive is None:
        update_current_gtfs_archive_if_necessary()

    return current_gtfs_archive


def update_gtfs_thread():
    """Background thread function to periodically update the GTFS archive.

    Runs in an infinite loop, checking every 60 seconds if the GTFS archive
    needs to be updated for a new service date.
    """
    while True:
        update_current_gtfs_archive_if_necessary()
        time.sleep(60)


def start_watching_gtfs():
    """Start the background GTFS update thread.

    Spawns a daemon thread that monitors the service date and updates
    the cached GTFS archive when the date changes (around 3 AM).
    """
    gtfs_thread = Thread(target=update_gtfs_thread, name="update_gtfs")
    gtfs_thread.start()
