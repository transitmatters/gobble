import { Mutex } from "async-mutex";
import config from "config";
import EventSource from "eventsource";
import { TripID, TripState } from "./types.js";
import * as gtfs from "./gtfs.js";
import * as io from "./io.js";
import * as util from "./util.js";
import { STOPS } from "./constants.js";

const API_KEY = config.get("mbta.v3_api_key");
const URL = "https://api-v3.mbta.com/vehicles?filter[route]=1";

function prune_state(state: Map<TripID, TripState>) {
  const today_service_date = util.service_date_iso8601(new Date());
  for(const [trip_id, trip_state] of state) {
    const trip_service_date = util.service_date_iso8601(trip_state.updated_at);
    if(today_service_date > trip_service_date) {
      state.delete(trip_id);
      console.log(`Pruned trip state for ${trip_id}; its service date was ${trip_service_date} (today is ${today_service_date})`);
    }
  }
}

async function main() {
  if (API_KEY === undefined) {
    throw new Error("Missing MBTA V3 API key; is MBTA_V3_API_KEY set?")
  }

  await gtfs.init();
  const stop_id_to_name = await gtfs.get_stop_id_map();

  console.log("Connecting to", URL);

  const eventSource = new EventSource(URL, {
    headers: {
      "Accept": "text/event-stream",
      "x-api-key": API_KEY,
    }
  });

  const mutex = new Mutex();

  const current_stop_state: Map<TripID, TripState> = await io.read_state() ?? new Map();

  eventSource.addEventListener("error", (e) => {
    throw new Error(e.message);
  });

  eventSource.addEventListener("update", async (e) => {    
    // Because updates can come at any time- we have to prevent a second update from
    // getting processed while the first is being written to disk
    // THIS CAN HAPPEN EVEN THOUGH NODE IS SINGLE-THREADED.
    const release = await mutex.acquire();

    try {
      prune_state(current_stop_state);

      const update = JSON.parse(e.data);
      const current_stop_sequence = update.attributes.current_stop_sequence;
      const direction_id = update.attributes.direction_id;
      const route_id = update.relationships.route.data.id;
      const stop_id = update.relationships.stop.data.id;
      const trip_id = update.relationships.trip.data.id;
      const vehicle_label = update.attributes.label;

      const updated_at = new Date(update.attributes.updated_at);
      const iso = updated_at.toISOString();

      let prev: TripState|undefined = current_stop_state.get(trip_id);
      if(prev === undefined) {
        prev = {
          stop_sequence: current_stop_sequence,
          stop_id,
          updated_at,
        };
        current_stop_state.set(trip_id, prev);
      }

      if (
        prev.stop_id !== stop_id &&
        prev.stop_sequence < current_stop_sequence
      ) {
        const stop_name_prev = stop_id_to_name.get(prev.stop_id);
        const service_date = util.service_date_iso8601(updated_at);

        if(STOPS.get(route_id)?.has(prev.stop_id)) {
          console.log(`[${iso}] Event: route=${route_id} trip_id=${trip_id} DEP stop=${stop_name_prev}`);
          try {
            await io.write_event(
              {
                service_date,
                route_id,
                trip_id,
                direction_id,
                stop_id: prev.stop_id,
                stop_sequence: current_stop_sequence,
                vehicle_id: "0", // TODO??
                vehicle_label,
                event_type: "DEP",
                event_time: updated_at,
                scheduled_headway: 0, // TODO
                scheduled_tt: 0 // TODO
              }
            );
          }
          catch (err) {
            console.error("Couldn't write event to disk: " + err);
          }
        }

        current_stop_state.set(trip_id, {
          stop_sequence: current_stop_sequence,
          stop_id,
          updated_at,
        });
      }
      await io.write_state(current_stop_state);
    }
    catch (err) {
      console.error("Error processing update: " + err.message + ". Payload: " + e.data);
    }
    finally {
      release();
    }
  });
}

main();
