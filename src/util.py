"""Utility functions for date/time handling and path generation.

This module provides helper functions for converting dates and timestamps,
generating output directory paths, and handling the MBTA's service date
concept (where dates roll over at 3 AM instead of midnight).

Attributes:
    EASTERN_TIME: ZoneInfo object for US/Eastern timezone.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import os
from ddtrace import tracer

from constants import ROUTES_CR, ROUTES_RAPID

EASTERN_TIME = ZoneInfo("US/Eastern")

# Initialize service date cache variables
_service_date_cache = None
_cache_hour = None


def to_dateint(date: date) -> int:
    """Convert a date to an integer in YYYYMMDD format.

    Args:
        date: A date object to convert.

    Returns:
        Integer representation of the date (e.g., 20220615 for June 15, 2022).
    """
    return int(str(date).replace("-", ""))


def output_dir_path(route_id: str, direction_id: str, stop_id: str, ts: datetime) -> str:
    """Generate the output directory path for storing event data.

    Creates a hierarchical path structure organized by transit mode, route,
    direction, stop, and date. The path format varies by mode to accommodate
    different naming conventions.

    Args:
        route_id: The MBTA route identifier.
        direction_id: The direction of travel (0 or 1).
        stop_id: The stop identifier.
        ts: Timestamp of the event, used to determine the service date.

    Returns:
        A relative path string for storing event data, e.g.,
        "daily-rapid-data/70063/Year=2022/Month=6/Day=15" for rapid transit or
        "daily-cr-data/CR-Fairmount_0_DB-2205-01/Year=2022/Month=6/Day=15" for
        commuter rail.
    """
    date = service_date(ts)

    # commuter rail lines have dashes in both route id and stop id, so use underscores as delimiter
    # ex, CR-Fairmount_0_DB-2205-01/
    if route_id in ROUTES_CR:
        delimiter = "_"
        stop_path = f"{route_id}{delimiter}{direction_id}{delimiter}{stop_id}"
        mode = "cr"
    # rapid transit doesn't need to be split by direction or line
    elif route_id in ROUTES_RAPID:
        stop_path = f"{stop_id}"
        mode = "rapid"
    else:
        delimiter = "-"
        stop_path = f"{route_id}{delimiter}{direction_id}{delimiter}{stop_id}"
        mode = "bus"

    return os.path.join(
        f"daily-{mode}-data",
        stop_path,
        f"Year={date.year}",
        f"Month={date.month}",
        f"Day={date.day}",
    )


@tracer.wrap()
def service_date(ts: datetime) -> date:
    """Convert a timestamp to an MBTA service date.

    The MBTA considers a service day to run from 3 AM to 3 AM the next day,
    rather than midnight to midnight. This function returns the appropriate
    service date for a given timestamp.

    Args:
        ts: A datetime object representing the event time. If timezone-naive,
            it is assumed to be in Eastern Time.

    Returns:
        The service date as a date object. Events between midnight and 3 AM
        are attributed to the previous calendar day's service.
    """
    # In practice a None TZ is UTC, but we want to be explicit
    # In many places we have an implied eastern
    ts = ts.replace(tzinfo=EASTERN_TIME)

    if ts.hour >= 3 and ts.hour <= 23:
        return date(ts.year, ts.month, ts.day)

    prior = ts - timedelta(days=1)
    return date(prior.year, prior.month, prior.day)


def get_current_service_date() -> date:
    """Get the current MBTA service date with hourly caching.

    Returns the service date for the current time, caching the result for
    the current hour to avoid repeated timezone conversions.

    Returns:
        The current service date as a date object.
    """
    global _service_date_cache, _cache_hour
    now = datetime.now(EASTERN_TIME)
    if now.hour != _cache_hour:
        _service_date_cache = service_date(now)
        _cache_hour = now.hour
    return _service_date_cache


def service_date_iso8601(ts: datetime) -> str:
    """Convert a timestamp to an ISO 8601 formatted service date string.

    Args:
        ts: A datetime object representing the event time.

    Returns:
        The service date in ISO 8601 format (e.g., "2022-06-15").
    """
    return service_date(ts).isoformat()
