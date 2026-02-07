# Configuration

Gobble is configured via a JSON file at `config/local.json`. A template is provided at `config/template.json`.

## Setup

```bash
cp config/template.json config/local.json
```

Then edit `config/local.json` with your values.

## Reference

```json
{
  "mbta": {
    "v3_api_key": null
  },
  "gtfs": {
    "dir": null,
    "refresh_interval_days": 7
  },
  "modes": ["rapid", "cr", "bus"],
  "DATADOG_TRACE_ENABLED": false
}
```

### `mbta.v3_api_key`

**Required.** Your MBTA V3 API key. Get one at [api-v3.mbta.com](https://api-v3.mbta.com/).

### `gtfs.dir`

Optional override for the GTFS archives storage directory. Defaults to `data/gtfs_archives/` when `null`.

### `gtfs.refresh_interval_days`

How often (in days) to check for a newer GTFS archive. The MBTA publishes new GTFS feeds regularly as schedules change. Defaults to `7`.

### `modes`

Which transit modes to stream. Any combination of:

| Value     | Description                                                                                                                                                                                                                                                      |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"rapid"` | Rapid transit: Red, Blue, Orange, Green-B/C/D/E, Mattapan                                                                                                                                                                                                        |
| `"cr"`    | Commuter rail: all lines                                                                                                                                                                                                                                         |
| `"bus"`   | Bus: all bus lines defined in [lines.txt](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#linestxt) and all stops defined in [checkpoints.txt](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#checkpointstxt) |

Useful for development — set `["rapid"]` to reduce API load and output volume.

### `DATADOG_TRACE_ENABLED`

Set to `true` to enable Datadog APM tracing and structured JSON logging. Should be `true` in production and `false` for local development.
