from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import os

from constants import ROUTES_CR, ROUTES_RAPID

EASTERN_TIME = ZoneInfo("US/Eastern")


def to_dateint(date: date) -> int:
    """turn date into 20220615 e.g."""
    return int(str(date).replace("-", ""))


def output_dir_path(route_id: str, direction_id: str, stop_id: str, ts: datetime) -> str:
    date = service_date(ts)

    # commuter rail lines have dashes in both route id and stop id, so use underscores as delimiter
    # ex, CR-Fairmount_0_DB-2205-01/
    if route_id in ROUTES_CR:
        delimiter = "_"
        mode = "cr"
    # rapid transit may rarely have dashes AND SPACES in stop id/route id!
    # ex, Green_D_1-Union Square-02
    elif route_id in ROUTES_RAPID:
        delimiter = "_"
        mode = "rapid"
    else:
        delimiter = "-"
        mode = "bus"

    return os.path.join(
        f"daily-{mode}-data",
        f"{route_id}{delimiter}{direction_id}{delimiter}{stop_id}",
        f"Year={date.year}",
        f"Month={date.month}",
        f"Day={date.day}",
    )


def service_date(ts: datetime) -> date:
    # In practice a None TZ is UTC, but we want to be explicit
    # In many places we have an implied eastern
    ts = ts.replace(tzinfo=EASTERN_TIME)

    if ts.hour >= 3 and ts.hour <= 23:
        return date(ts.year, ts.month, ts.day)

    prior = ts - timedelta(days=1)
    return date(prior.year, prior.month, prior.day)


def get_current_service_date() -> date:
    return service_date(datetime.now(EASTERN_TIME))


def service_date_iso8601(ts: datetime) -> str:
    return service_date(ts).isoformat()
