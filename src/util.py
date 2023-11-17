from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import os

EASTERN_TIME = ZoneInfo("America/New_York")

def to_dateint(date: date):
    """turn date into 20220615 e.g."""
    return int(str(date).replace("-", ""))

def output_dir_path(route_id: str, direction_id: str, stop_id: str, ts: datetime):
  date = service_date(ts)

  return os.path.join(
    f"{route_id}-{direction_id}-{stop_id}",
    f"Year={date.year}",
    f"Month={date.month}",
    f"Day={date.day}"
  )

def service_date(ts: datetime) -> date:
  localized = ts.astimezone(EASTERN_TIME)
  if localized.hour >= 4 and localized.hour <= 23:
     return date(ts.year, ts.month, ts.day)
  
  prior = (localized - timedelta(days=1))
  return date(prior.year, prior.month, prior.day)

def service_date_iso8601(ts: datetime) -> str:
  return service_date(ts).isoformat()
