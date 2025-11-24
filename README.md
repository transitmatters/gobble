# gobble

![lint](https://github.com/transitmatters/gobble/actions/workflows/lint.yml/badge.svg?branch=main)
![test](https://github.com/transitmatters/gobble/actions/workflows/test.yml/badge.svg?branch=main)

![Screenshot in action](docs/screenshot.png)

Gobble is a service that reads transit vehicle position data and writes arrival/departure events to a format that can be understood by the [TransitMatters Data Dashboard](https://github.com/transitmatters/t-performance-dash).

Gobble supports two data ingestion modes:

- **MBTA SSE API** (default): Uses the [MBTA V3 Streaming API](https://www.mbta.com/developers/v3-api/streaming) for real-time vehicle updates via Server-Sent Events
- **GTFS-RT**: Uses any GTFS-Realtime VehiclePositions feed for standardized transit data ingestion

## Requirements to develop locally

- Python 3.12
- [poetry](https://python-poetry.org/)

## Development Instructions

### Using MBTA SSE API (Default)

1. Duplicate `config/template.json` into `config/local.json`, and add your MBTA V3 API key:

   ```json
   {
     "mbta": {
       "v3_api_key": "YOUR_API_KEY_HERE"
     },
     "use_gtfs_rt": false
   }
   ```

2. In the root directory, run `poetry install` to install dependencies
3. Run `poetry run python3 src/gobble.py` to start.
4. Output will be in `data/` in your current working directory. Good luck!

### Using GTFS-RT (Generic Transit Agencies)

1. Duplicate `config/youragency_template.json` into `config/local.json`, and configure GTFS-RT settings:

```json
{
  "agency": "septa_regionalrail",
  "GTFS_ARCHIVES_PREFIX": "http://127.0.0.1:8000",
  "GTFS_ARCHIVES_FILENAME": "archived_feeds.txt?feed_id=mdb-503",
  "mbta": {
    "v3_api_key": null
  },
  "gtfs": {
    "dir": null,
    "refresh_interval_days": 7
  },
  "use_gtfs_rt": true,
  "gtfs_rt": {
    "mobility_database_id": "mdb-503",
    "feed_url": "<https://www3.septa.org/gtfsrt/septarail-pa-us/Vehicle/rtVehiclePosition.pb>",
    "api_key": null,
    "api_key_method": "none",
    "polling_interval": 10
  },
  "DATADOG_TRACE_ENABLED": false
}

```

   Configuration options:

- `feed_url`: URL of the GTFS-RT VehiclePositions feed (required)
- `api_key`: API key for authentication (optional, if required by your feed)
- `api_key_method`: How to pass the API key to the server (default: `"header"`)
  - `"header"`: Pass API key as an HTTP header
  - `"query"`: Pass API key as a URL query parameter
  - `"bearer"`: Pass API key as a Bearer token in the Authorization header
  - `"none"`: No authentication (omit `api_key`)
- `api_key_param_name`: Header name or query parameter name (default: `"X-API-KEY"`)
  - Used for `"header"` method: custom header name
  - Used for `"query"` method: query parameter name
  - Ignored for `"bearer"` and `"none"` methods
- `polling_interval`: Seconds between feed polls (default: 10)

#### API Key Authentication Examples

   **Example 1: Header-based authentication (default)**

   ```json
   "gtfs_rt": {
     "feed_url": "https://api.example.com/gtfs-rt/positions",
     "api_key": "your-secret-key",
     "api_key_method": "header",
     "api_key_param_name": "X-API-KEY"
   }
   ```

   This sends: `X-API-KEY: your-secret-key`

   **Example 2: Query parameter authentication**

   ```json
   "gtfs_rt": {
     "feed_url": "https://api.example.com/gtfs-rt/positions",
     "api_key": "your-secret-key",
     "api_key_method": "query",
     "api_key_param_name": "api_key"
   }
   ```

   This transforms the URL to: `https://api.example.com/gtfs-rt/positions?api_key=your-secret-key`

   **Example 3: Bearer token authentication**

   ```json
   "gtfs_rt": {
     "feed_url": "https://api.example.com/gtfs-rt/positions",
     "api_key": "your-access-token",
     "api_key_method": "bearer"
   }
   ```

   This sends: `Authorization: Bearer your-access-token`

   **Example 4: No authentication**

   ```json
   "gtfs_rt": {
     "feed_url": "https://open-transit.com/gtfs-rt/positions",
     "api_key_method": "none"
   }
   ```

   No API key is sent with requests

2. In the root directory, run `poetry install` to install dependencies
3. Run `poetry run python3 src/gobble.py` to start.
4. Output will be in `data/` in your current working directory.

### GTFS Static Schedule

Gobble enriches real-time events with GTFS static schedule data (headways, scheduled times).

- For MBTA: Automatically downloads from `https://cdn.mbta.com/archive/`
- For other agencies: Configure a GTFS static feed URL (future enhancement)

The GTFS archive is refreshed every 7 days by default (configurable via `refresh_interval_days`).

### Testing

Run the test suite with:

```bash
poetry run pytest src/tests/
```

### Linting

You can run the linter against any code changes with the following commands

```bash
poetry run flake8 src
poetry run black --check src
```

## Support TransitMatters

If you've found this app helpful or interesting, please consider [donating](https://transitmatters.org/donate) to TransitMatters to help support our mission to provide data-driven advocacy for a more reliable, sustainable, and equitable transit system in Metropolitan Boston.
