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

GTFS_ARCHIVES_PREFIX = CONFIG["GTFS_ARCHIVES_PREFIX"]
GTFS_ARCHIVES_FILENAME = CONFIG["GTFS_ARCHIVES_FILENAME"]

# defining these columns in particular becasue we use them everywhere
RTE_DIR_STOP = ["route_id", "direction_id", "stop_id"]

# only fetch required columns from gtfs csv's to reduce memory usage
STOP_TIMES_COLS = [
    "stop_id",
    "trip_id",
    "arrival_time",
    "departure_time",
    "stop_id",
    "stop_sequence",
]


def _group_df_by_column(df: pd.DataFrame, column_name: str) -> Dict[str, pd.DataFrame]:
    return {key: df_group for key, df_group in df.groupby(column_name)}


def _get_empty_df_with_same_columns(df: pd.DataFrame) -> pd.DataFrame:
    empty_df = df.copy(deep=False)
    empty_df.drop(empty_df.index, inplace=True)
    return empty_df


@dataclass
class GtfsArchive:
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
            self._stop_times_by_route_id[route_id] = self.stop_times[
                self.stop_times.trip_id.isin(trip_ids_for_route)
            ]

    def stop_times_by_route_id(self, route_id: str):
        return self._stop_times_by_route_id.get(route_id, self._stop_times_empty)

    def trips_by_route_id(self, route_id: str):
        return self._trips_by_route_id.get(route_id, self._trips_empty)


@tracer.wrap()
def _download_gtfs_archives_list() -> Optional[pd.DataFrame]:
    """Downloads list of GTFS archive urls. This file will get overwritten."""
    archives_df = None
    try:
        archives_df = pd.read_csv(urljoin(GTFS_ARCHIVES_PREFIX, GTFS_ARCHIVES_FILENAME))
        try:
            archives_df.to_csv(MAIN_DIR / GTFS_ARCHIVES_FILENAME)
        except (PermissionError, OSError, IOError) as e:
            logger.error(
                f"Failed to write GTFS archives file due to permission error: {e}"
            )
            logger.warning(
                "Continuing with downloaded archives data without saving to disk"
            )
        return archives_df
    except Exception as e:
        logger.error(f"Failed to download GTFS archives list: {e}")
        return None


def to_dateint(date: datetime.date) -> int:
    """turn date into 20220615 e.g."""
    return int(str(date).replace("-", ""))


def _find_most_recent_gtfs_archive() -> Optional[pathlib.Path]:
    """
    Find the most recent GTFS archive directory that exists and is accessible.
    Returns None if no accessible archives are found.
    """
    try:
        # Get all directories in the GTFS archives folder
        archive_dirs = [
            d
            for d in MAIN_DIR.iterdir()
            if d.is_dir() and d.name != "archived_feeds.txt"
        ]

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
def get_gtfs_archive(dateint: int):
    """
    Determine which GTFS archive corresponds to the date.
    Returns that archive folder, downloading if it doesn't yet exist.
    Falls back to most recent available archive if permission errors occur.
    """
    matches = pd.DataFrame()
    should_refetch = False

    try:
        if (MAIN_DIR / GTFS_ARCHIVES_FILENAME).exists():
            archives_df = pd.read_csv(MAIN_DIR / GTFS_ARCHIVES_FILENAME)
            matches = archives_df[
                (archives_df.feed_start_date <= dateint)
                & (archives_df.feed_end_date >= dateint)
            ]

            # Check if we should refetch based on time since feed start date
            if len(matches) > 0:
                current_feed = matches.iloc[0]
                feed_start_date = datetime.datetime.strptime(
                    str(int(current_feed.feed_start_date)), "%Y%m%d"
                ).date()
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
                logger.info(
                    "No matches found in existing GTFS archives. Fetching latest archives."
                )
            else:
                logger.info("Fetching latest archives to check for updates.")
            archives_df = _download_gtfs_archives_list()

            # If download failed, try to use fallback
            if archives_df is None:
                logger.warning(
                    "Failed to download GTFS archives list. Attempting to use most recent available archive."
                )
                fallback_archive = _find_most_recent_gtfs_archive()
                if fallback_archive:
                    logger.info(f"Using fallback GTFS archive: {fallback_archive}")
                    return fallback_archive
                else:
                    logger.error("No accessible GTFS archives found. Cannot continue.")
                    raise RuntimeError(
                        "Cannot download GTFS archives and no local archives available"
                    )

            matches = archives_df[
                (archives_df.feed_start_date <= dateint)
                & (archives_df.feed_end_date >= dateint)
            ]

        if len(matches) == 0:
            raise ValueError(f"No GTFS archive found for date {dateint}")

        archive_url = matches.iloc[0].archive_url
        archive_name = pathlib.Path(archive_url).stem

        if (MAIN_DIR / archive_name).exists():
            logger.info(
                f"GTFS archive for {dateint} already downloaded: {archive_name}"
            )
            return MAIN_DIR / archive_name

        # else we have to download it
        logger.info(f"Downloading GTFS archive for {dateint}: {archive_url}")
        zipfile, _ = urllib.request.urlretrieve(archive_url)
        shutil.unpack_archive(
            zipfile, extract_dir=(MAIN_DIR / archive_name), format="zip"
        )
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
        logger.warning(
            "Attempting to use most recent available GTFS archive as fallback"
        )

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
    """
    Read calendar.txt to determine which services ran on the given date.
    Also, incorporate exceptions from calendar_dates.txt for holidays, etc.
    calendar.txt is optional in GTFS; if missing, rely on calendar_dates.txt only.
    """
    dateint = to_dateint(date)
    day_of_week = date.strftime("%A").lower()

    services = []
    calendar_path = archive_dir / "calendar.txt"
    if calendar_path.exists():
        cal = pd.read_csv(calendar_path)
        current_services = cal[(cal.start_date <= dateint) & (cal.end_date >= dateint)]
        services = current_services[
            current_services[day_of_week] == 1
        ].service_id.tolist()

    calendar_dates_path = archive_dir / "calendar_dates.txt"
    if calendar_dates_path.exists():
        exceptions = pd.read_csv(calendar_dates_path)
        exceptions = exceptions[exceptions.date == dateint]
        additions = exceptions[exceptions.exception_type == 1].service_id.tolist()
        subtractions = exceptions[exceptions.exception_type == 2].service_id.tolist()

        services = (set(services) - set(subtractions)) | set(additions)

    return list(services)


@tracer.wrap()
def read_gtfs(
    date: datetime.date, routes_filter: Optional[Set[str]] = None
) -> GtfsArchive:
    """
    Given a date, this function will:
    - Find the appropriate gtfs archive (downloading if necessary)
    - Determine which services ran on that date
    - Return three dataframes containing just the trips and stop_times that ran on that date, and corresponding stop information
    If a route filter is applied, only return trips and stop information relevent to supplied routes. Otherwise, return all services.
    """
    dateint = to_dateint(date)
    logger.info(f"Reading GTFS archive for {date}")

    archive_dir = get_gtfs_archive(dateint)
    services = get_services(date, archive_dir)

    # specify dtypes to avoid warnings
    trips = pd.read_csv(
        archive_dir / "trips.txt",
        dtype={
            "trip_short_name": str,
            "block_id": str,
            "route_id": str,
            "direction_id": int,
            "trip_id": str,
        },
    )
    trips = trips[trips.service_id.isin(services)]
    # filter by routes
    if routes_filter:
        trips = trips[trips.route_id.isin(routes_filter)]

    stops = pd.read_csv(archive_dir / "stops.txt", dtype={"stop_id": str})
    stops["stop_id"] = stops["stop_id"].str.strip()

    stop_times = pd.read_csv(
        archive_dir / "stop_times.txt",
        dtype={"trip_id": str, "stop_id": str},
        usecols=STOP_TIMES_COLS,
    )
    stop_times["stop_id"] = stop_times["stop_id"].str.strip()
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    stop_times.arrival_time = pd.to_timedelta(stop_times.arrival_time)
    stop_times.departure_time = pd.to_timedelta(stop_times.departure_time)

    return GtfsArchive(
        trips=trips, stop_times=stop_times, stops=stops, service_date=date
    )


@tracer.wrap()
def batch_add_gtfs_headways(
    events_df: pd.DataFrame, trips: pd.DataFrame, stop_times: pd.DataFrame
) -> pd.DataFrame:
    """A batch implementation of add_gtfs_headways--this will probably never be used, but we include it just in case."""
    results = []

    # we have to do this day-by-day because gtfs changes so often
    for service_date, days_events in events_df.groupby("service_date"):
        # filter out the trips of interest
        relevant_trips = trips[trips.route_id.isin(days_events.route_id)]

        # take only the stops from those trips (adding route and dir info)
        trip_info = relevant_trips[["trip_id", "route_id", "direction_id"]]
        gtfs_stops = stop_times.merge(trip_info, on="trip_id", how="right")

        # drop rows with null values in merge key columns to prevent merge_asof failures
        gtfs_stops = gtfs_stops.dropna(subset=RTE_DIR_STOP + ["arrival_time"])

        # calculate gtfs headways
        gtfs_stops = gtfs_stops.sort_values(by="arrival_time")
        headways = gtfs_stops.groupby(RTE_DIR_STOP).arrival_time.diff()
        # the first stop of a trip doesnt technically have a real scheduled headway, so we set to empty string
        headways = headways.fillna("")
        gtfs_stops["scheduled_headway"] = headways.dt.seconds

        # calculate gtfs traveltimes
        trip_start_times = gtfs_stops.groupby("trip_id").arrival_time.transform("min")
        gtfs_stops["scheduled_tt"] = (
            gtfs_stops.arrival_time - trip_start_times
        ).dt.seconds

        # assign each actual timepoint a scheduled headway
        # merge_asof 'backward' matches the previous scheduled value of 'arrival_time'
        days_events["arrival_time"] = days_events.event_time - pd.Timestamp(
            service_date
        ).tz_localize(EASTERN_TIME)
        augmented_events = pd.merge_asof(
            days_events.sort_values(by="arrival_time"),
            gtfs_stops[RTE_DIR_STOP + ["arrival_time", "scheduled_headway"]],
            on="arrival_time",
            direction="backward",
            by=RTE_DIR_STOP,
        )

        # assign each actual trip a scheduled trip_id, based on when it started the route
        route_starts = days_events.loc[
            days_events.groupby("trip_id").event_time.idxmin()
        ]
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
        augmented_events["scheduled_trip_id"] = augmented_events.trip_id.map(
            trip_id_map
        )
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
def add_gtfs_headways(
    event_df: pd.DataFrame, all_trips: pd.DataFrame, all_stops: pd.DataFrame
) -> pd.DataFrame:
    """
    This will calculate scheduled headway and traveltime information
    from gtfs for the routes we care about, and then match our actual
    events to the scheduled values. This matching is done based on
    time-of-day, so is not an excact match. Luckily, pandas helps us out
    with merge_asof.
    https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html
    This function is ADAPTED from historical bus headway calculations
    https://github.com/transitmatters/t-performance-dash/blob/ebecaca071b39d8140296545f2e5b287915bc60d/server/bus/gtfs_archive.py#L90

    NB 1: event times are converted to pd timestamps in this fuction for pandas merge manipulation,
    but will be converted back into datetime.datetime for serialization purposes. careful!
    NB 2: ensure that all times are in US/Eastern!
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

    # drop rows with null values in merge key columns to prevent merge_asof failures
    gtfs_stops = gtfs_stops.dropna(subset=RTE_DIR_STOP + ["arrival_time"])

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
    event_df["arrival_time"] = event_df.event_time - pd.Timestamp(
        service_date
    ).tz_localize(EASTERN_TIME)
    event_df = event_df.sort_values(by="arrival_time")
    augmented_event = pd.merge_asof(
        event_df,
        gtfs_stops[RTE_DIR_STOP + ["arrival_time", "scheduled_headway"]],
        on="arrival_time",
        direction="backward",
        by=RTE_DIR_STOP,
    )

    # assign each actual trip a scheduled trip_id, based on when it started the route
    route_starts = event_df[RTE_DIR_STOP + ["trip_id", "arrival_time"]].sort_values(
        by="arrival_time"
    )

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
    global current_gtfs_archive
    global write_gtfs_archive_lock
    with write_gtfs_archive_lock:
        gtfs_service_date = util.service_date(datetime.datetime.now(util.EASTERN_TIME))
        needs_update = (
            current_gtfs_archive is None
            or current_gtfs_archive.service_date != gtfs_service_date
        )
        if needs_update:
            if current_gtfs_archive is None:
                logger.info(f"Downloading GTFS archive for {gtfs_service_date}")
            else:
                logger.info(
                    f"Updating GTFS archive from {current_gtfs_archive.service_date} to {gtfs_service_date}"
                )
            current_gtfs_archive = read_gtfs(
                gtfs_service_date, routes_filter=ALL_ROUTES
            )


def get_current_gtfs_archive() -> GtfsArchive:
    global current_gtfs_archive
    if current_gtfs_archive is None:
        update_current_gtfs_archive_if_necessary()

    return current_gtfs_archive


def update_gtfs_thread():
    while True:
        update_current_gtfs_archive_if_necessary()
        time.sleep(60)


def start_watching_gtfs():
    gtfs_thread = Thread(target=update_gtfs_thread, name="update_gtfs")
    gtfs_thread.start()
