import EventSource from "eventsource";
import * as output from "./output.js";
import * as gtfs from "./gtfs.js";

const API_KEY = process.env.MBTA_V3_API_KEY;

const URL = "https://api-v3.mbta.com/vehicles?filter[route]=66";
// const URL = "https://api-v3.mbta.com/vehicles";


async function main() {
  if (API_KEY === undefined) {
    throw new Error("Missing MBTA V3 API key; is MBTA_V3_API_KEY set?")
  }

  await gtfs.init();
  const stop_id_to_name = await gtfs.get_stop_id_map();

  console.log("Connecting to", URL);

  const es = new EventSource(URL, {
    headers: {
      "Accept": "text/event-stream",
      "x-api-key": API_KEY,
    }
  });

  const current_stop_state: Map<string, string> = new Map();

  es.addEventListener("error", (e) => {
    throw new Error(e.message);
  });

  es.addEventListener("update", async (e) => {
    try {
      const update = JSON.parse(e.data);
      const trip_id = update.relationships.trip.data.id;
      const route_id = update.relationships.route.data.id;

      const stop_id_prev = current_stop_state.get(trip_id);
      const stop_id_now = update.relationships.stop.data.id;

      if (stop_id_prev !== stop_id_now && stop_id_prev !== undefined) {
        const stop_name_prev = stop_id_to_name.get(stop_id_prev);
        const ts = new Date();
        const iso = ts.toISOString();
        const service_date: string = iso.substring(0, 10);

        console.log(`[${iso}] Writing event: route=${route_id} trip_id=${trip_id} DEP stop=${stop_name_prev}`);
        try {
          await output.write(
            {
              service_date,
              route_id,
              trip_id,
              direction_id: 0, // TODO
              stop_id: stop_id_prev,
              stop_sequence: 0, // TODO
              vehicle_id: "0", // TODO
              vehicle_label: "0", // TODO
              event_type: "DEP",
              event_time: ts,
              scheduled_headway: 0, // TODO
              scheduled_tt: 0 // TODO
            }
          );
        }
        catch (err) {
          console.error("Couldn't write to disk: " + err);
        }
      }
      current_stop_state.set(trip_id, stop_id_now);
    }
    catch (err) {
      console.error("Error processing update" + err.message);
    }
  });
}

main();
