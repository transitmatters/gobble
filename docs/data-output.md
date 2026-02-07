# Data Output

Gobble writes processed events as CSV files organized in a hierarchical directory structure under `data/`.

## Directory structure

```
data/
├── daily-rapid-data/
│   └── {stop_id}/
│       └── Year={year}/Month={month}/Day={day}/
│           └── events.csv
├── daily-cr-data/
│   └── {route_id}_{direction_id}_{stop_id}/
│       └── Year={year}/Month={month}/Day={day}/
│           └── events.csv
├── daily-bus-data/
│   └── {route_id}-{direction_id}-{stop_id}/
│       └── Year={year}/Month={month}/Day={day}/
│           └── events.csv
├── gtfs_archives/
│   └── ...
└── trip_states/
    └── {route_id}.json
```

Each mode uses a slightly different path convention:

- **Rapid transit**: Keyed by `stop_id` only (direction/line is implicit in the stop)
- **Commuter rail**: Underscore-delimited `route_id`, `direction_id`, `stop_id` (because route and stop IDs contain dashes)
- **Bus**: Dash-delimited `route_id`, `direction_id`, `stop_id`

## CSV schema

Each `events.csv` contains the following columns:

| Column                 | Type       | Description                                                |
| ---------------------- | ---------- | ---------------------------------------------------------- |
| `service_date`         | `date`     | MBTA service date (3 AM to 3 AM)                           |
| `route_id`             | `string`   | MBTA route identifier (e.g., `Red`, `CR-Fairmount`, `57`)  |
| `trip_id`              | `string`   | MBTA trip identifier                                       |
| `direction_id`         | `int`      | Direction of travel: `0` or `1`                            |
| `stop_id`              | `string`   | MBTA stop identifier                                       |
| `stop_sequence`        | `int`      | Position of this stop in the trip's sequence               |
| `vehicle_id`           | `string`   | Vehicle identifier (currently always `"0"`)                |
| `vehicle_label`        | `string`   | Human-readable vehicle number                              |
| `event_type`           | `string`   | `ARR` (arrival) or `DEP` (departure)                       |
| `event_time`           | `datetime` | Timestamp of the event (Eastern Time)                      |
| `scheduled_headway`    | `float`    | Scheduled seconds since previous trip at this stop         |
| `scheduled_tt`         | `float`    | Scheduled travel time in seconds from trip start           |
| `vehicle_consist`      | `string`   | Pipe-delimited car numbers for multi-car trains            |
| `occupancy_status`     | `string`   | Pipe-delimited occupancy status per car (if available)     |
| `occupancy_percentage` | `string`   | Pipe-delimited occupancy percentage per car (if available) |

## S3 destination

In production, files are uploaded every 30 minutes to:

```
s3://tm-mbta-performance/Events-live/{relative_path}.gz
```

Files are gzip-compressed before upload.
