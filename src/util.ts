import { DateTime } from "luxon";

const EASTERN_TIME = "America/New_York";

function service_date_str(date_js: Date) {
  const date = DateTime.fromJSDate(date_js).setZone(EASTERN_TIME);
  if(date.hour >= 4 && date.hour <= 23) {
    return date.toISODate()!;
  }

  return date.minus({ days: 1 }).toISODate()!;
}

export { service_date_str };
