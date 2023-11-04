import config from "config";
import EventSource from "eventsource";
import * as io from "./io.js";
import * as gtfs from "./gtfs.js";
import { TripID, TripState } from "./types.js";
import * as util from "./util.js";

const API_KEY = config.get("mbta.v3_api_key");
const MAX_UPDATE_AGE_MS = 180 * 1000; // 3 minutes
const URL = "https://api-v3.mbta.com/vehicles?filter[route]=66";

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

  const current_stop_state: Map<TripID, TripState> = await io.read_state() ?? new Map();

  eventSource.addEventListener("error", (e) => {
    throw new Error(e.message);
  });

  eventSource.addEventListener("update", async (e) => {
    try {
      const update = JSON.parse(e.data);
      const current_stop_sequence = update.attributes.current_stop_sequence;
      const direction_id = update.attributes.direction_id;
      const route_id = update.relationships.route.data.id;
      const stop_id = update.relationships.stop.data.id;
      const trip_id = update.relationships.trip.data.id;
      const vehicle_label = update.attributes.label;

      const updated_at = new Date(update.attributes.updated_at);
      const iso = updated_at.toISOString();

      const prev = current_stop_state.get(trip_id);

      if (
        prev !== undefined &&
        prev.stop_id !== stop_id &&
        updated_at.getTime() - prev.updated_at.getTime() <= MAX_UPDATE_AGE_MS
      ) {
        const stop_name_prev = stop_id_to_name.get(prev.stop_id);
        const service_date = util.service_date_str(updated_at);

        console.log(`[${iso}] Writing event: route=${route_id} trip_id=${trip_id} DEP stop=${stop_name_prev}`);
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
          console.error("Couldn't write to disk: " + err);
        }
      }
      current_stop_state.set(trip_id, {
        stop_id,
        updated_at
      });
      await io.write_state(current_stop_state);
    }
    catch (err) {
      console.error("Error processing update" + err.message);
    }
  });
}

main();
