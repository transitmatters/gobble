import { DateTime } from "luxon";
import * as path from "node:path";

const EASTERN_TIME = "America/New_York";

function output_dir_path(output_dir: string, route_id: string, direction_id: number, stop_id: string, ts: Date) {
  const date = service_date(ts);

  return path.join(
    output_dir,
    `${route_id}-${direction_id}-${stop_id}`,
    `Year=${date.year}`,
    `Month=${date.month}`,
    `Day=${date.day}`
  );
}

function service_date(date_js: Date) {
  const date = DateTime.fromJSDate(date_js).setZone(EASTERN_TIME);
  if(date.hour >= 4 && date.hour <= 23) {
    return date.startOf("day");
  }

  return date.minus({ days: 1 }).startOf("day");
}

function service_date_iso8601(date_js: Date) {
  return service_date(date_js).toISODate()!;
}

export { output_dir_path, service_date_iso8601 };
