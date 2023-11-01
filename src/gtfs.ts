import { importGtfs, getStops } from "gtfs";

const GTFS_UNZIPPED_PATH = process.env.MBTA_GTFS_UNZIPPED;
const GTFS_LOADER_CONFIG = {
  "agencies": [
    {
      "path": GTFS_UNZIPPED_PATH,
      "exclude": [
        "agency",
        "areas",
        "attributions",
        "calendar_attributes",
        "calendar_dates",
        "calendar",
        "checkpoints",
        "directions",
        "facilities_properties_definitions",
        "facilities_properties",
        "facilities",
        "fare_attributes",
        "fare_leg_rules",
        "fare_media",
        "fare_products",
        "fare_rules",
        "fare_transfer_rules",
        "feed_info",
        "frequencies",
        "levels",
        "lines",
        "linked_datasets",
        "multi_route_trips",
        "pathways",
        "route_patterns",
        "routes",
        "shapes",
        "stop_areas",
        "stop_times",
        "transfers",
        "translations",
        "trips_properties_definitions",
        "trips_properties",
        "trips",
        // "stops", // We actually want this one, so it's excluded from the exclude list! :-)
      ]
    }
  ],
  // "verbose": false
};

async function init() {
  if (GTFS_UNZIPPED_PATH === undefined) {
    throw new Error("Missing path to GTFS; is MBTA_GTFS_UNZIPPED set?")
  }

  await importGtfs(GTFS_LOADER_CONFIG);
}

async function get_stop_id_map(): Promise<Map<string, string>> {
  const stops = getStops();
  const stop_id_to_name: Map<string, string> = new Map();

  for (const stop of stops) {
    stop_id_to_name.set(stop.stop_id, stop.stop_name);
  }

  return stop_id_to_name;
}

export { init, get_stop_id_map };
