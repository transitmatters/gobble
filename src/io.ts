import * as path from "node:path";
import * as fs from "node:fs/promises";
import { CSVEvent, Event, TripID, TripState } from "./types.js";

const CSV_FILENAME = "events.csv";
const STATE_FILENAME = "state.json";
const OUTPUT_DIR = "output";

function dir_path(route_id: string, direction_id: number, stop_id: string, ts: Date) {
  const year = ts.getUTCFullYear();
  const month = ts.getUTCMonth() + 1;
  const day = ts.getUTCDate();

  return path.join(
    OUTPUT_DIR,
    `${route_id}-${direction_id}-${stop_id}`,
    `Year=${year}`,
    `Month=${month}`,
    `Day=${day}`
  );
}

async function write_event(event: Event) {
  const writable: CSVEvent = {
    ...event,
    event_time: event.event_time.toISOString()
  };
  const csv_line = Object.values(writable).join(",") + "\n";
  const dirname = dir_path(event.route_id, event.direction_id, event.stop_id, event.event_time);
  const pathname = path.join(dirname, CSV_FILENAME);

  await fs.mkdir(dirname, { recursive: true })
  return fs.writeFile(pathname, csv_line, { flag: "a+" });
}

async function read_state() {
  try {
    const pathname = path.join(OUTPUT_DIR, STATE_FILENAME);
    return new Map(JSON.parse((await fs.readFile(pathname)).toString()));
  }
  catch(err) {
    console.error("Error reading state from disk:", err.message);
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
