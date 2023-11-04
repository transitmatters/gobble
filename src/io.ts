import * as path from "node:path";
import * as fs from "node:fs/promises";
import { output_dir_path } from "./util.js";
import { CSVEvent, Event, TripID, TripState } from "./types.js";

const CSV_FILENAME = "events.csv";
const STATE_FILENAME = "state.json";
const OUTPUT_DIR = "output";

async function write_event(event: Event) {
  const writable: CSVEvent = {
    ...event,
    event_time: event.event_time.toISOString()
  };
  const csv_line = Object.values(writable).join(",") + "\n";
  const dirname = output_dir_path(
    OUTPUT_DIR, event.route_id, event.direction_id, event.stop_id, event.event_time);
  const pathname = path.join(dirname, CSV_FILENAME);

  await fs.mkdir(dirname, { recursive: true })
  return fs.writeFile(pathname, csv_line, { flag: "a+" });
}

function json_decode(key, value) {
  if(key === "updated_at") {
    return new Date(value);
  }
  return value;
}

async function read_state() {
  try {
    const pathname = path.join(OUTPUT_DIR, STATE_FILENAME);
    return new Map(JSON.parse((await fs.readFile(pathname)).toString(), json_decode));
  }
  catch(err) {
    if(err.code !== "ENOENT") {
      console.error("Error reading state from disk:", err.message);
    }
  }

  return undefined;
}

async function write_state(state: Map<TripID, TripState>) {
  const pathname = path.join(OUTPUT_DIR, STATE_FILENAME);
  await fs.mkdir(OUTPUT_DIR, { recursive: true })
  return fs.writeFile(
    pathname,
    JSON.stringify(Array.from(state), null, 2)
  );
}


export { write_event, read_state, write_state };
