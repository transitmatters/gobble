from datetime import datetime
from typing import Dict
import json
import pandas as pd
import requests
import sseclient

from constants import STOPS
from config import CONFIG
import gtfs
import disk
import util

API_KEY = CONFIG["mbta"]["v3_api_key"]
HEADERS = {
  "X-API-KEY": API_KEY,
  "Accept": "text/event-stream"
  }
URL = "https://api-v3.mbta.com/vehicles?filter[route]=1"

def get_stop_name(stops_df, stop_id):
   return stops_df[stops_df["stop_id"] == stop_id].iloc[0].stop_name

def main():
  current_stop_state: Dict = disk.read_state()

  # Download the gtfs bundle before we proceed so we don't have to wait
  print("Downloading GTFS bundle if necessary...")
  scheduled_trips, scheduled_stop_times, stops = gtfs.read_gtfs(util.service_date(datetime.now()))

  print(f"Connecting to {URL}...")
  client = sseclient.SSEClient(requests.get(
        URL,
        headers=HEADERS,
        stream=True))
  
  for event in client.events():
    if event.event != "update":
      continue

    update = json.loads(event.data)
    current_stop_sequence = update["attributes"]["current_stop_sequence"]
    direction_id = update["attributes"]["direction_id"]
    route_id = update["relationships"]["route"]["data"]["id"]
    stop_id = update["relationships"]["stop"]["data"]["id"]
    trip_id = update["relationships"]["trip"]["data"]["id"]
    vehicle_label = update["attributes"]["label"]
    updated_at = datetime.fromisoformat(update["attributes"]["updated_at"])

    prev = current_stop_state.get(trip_id, {
      "stop_sequence": current_stop_sequence,
      "stop_id": stop_id,
      "updated_at": updated_at,
    })
    # current_stop_state updated_at is isofmt str, not datetime.
    if isinstance(prev["updated_at"], str): 
        prev["updated_at"] = datetime.fromisoformat(prev["updated_at"])

    if prev["stop_id"] != stop_id and prev["stop_sequence"] < current_stop_sequence:
      stop_name_prev = get_stop_name(stops, prev["stop_id"])
      service_date = util.service_date(updated_at)
    
      if prev["stop_id"] in STOPS[route_id] or True:
        print(f"[{updated_at.isoformat()}] Event: route={route_id} trip_id={trip_id} DEP stop={stop_name_prev}")

        # write the event here
        df = pd.DataFrame([{
          "service_date": service_date,
          "route_id": route_id,
          "trip_id": trip_id,
          "direction_id": direction_id,
          "stop_id": prev["stop_id"],
          "stop_sequence": current_stop_sequence,
          "vehicle_id": "0", # TODO??
          "vehicle_label": vehicle_label,
          "event_type": "DEP",
          "event_time": updated_at,
        }], index=[0])

        headway_adjusted_df = gtfs.add_gtfs_headways(df, scheduled_trips, scheduled_stop_times)
        event = headway_adjusted_df.to_dict("records")[0]
        disk.write_event(event)

    current_stop_state[trip_id] = {
      "stop_sequence": current_stop_sequence,
      "stop_id": stop_id,
      "updated_at": updated_at,
    }
    
    # write the state out here
    disk.write_state(current_stop_state)

main()
