# Gobble

Gobble is a service that reads the [MBTA V3 Streaming API](https://www.mbta.com/developers/v3-api/streaming) for all train and bus events, and writes them out to a format that can be understood by the [TransitMatters Data Dashboard](https://github.com/transitmatters/t-performance-dash).

![Screenshot in action](screenshot.png)

## What it does

1. **Streams** real-time vehicle positions from the MBTA API using Server-Sent Events (SSE)
2. **Detects** arrival and departure events by comparing successive vehicle states
3. **Enriches** events with scheduled headway and travel time data from GTFS
4. **Writes** processed events to CSV files organized by route, direction, stop, and date
5. **Uploads** data to AWS S3 for consumption by the Data Dashboard

## Supported transit modes

- **Rapid transit** — Red, Blue, Orange, Green (B/C/D/E), and Mattapan lines
- **Commuter rail** — All MBTA commuter rail lines
- **Bus** — All bus lines defined in [lines.txt](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#linestxt) and all stops defined in [checkpoints.txt](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#checkpointstxt)

!!! note "About bus lines"
    `lines.txt` and `checkpoints.txt` are MBTA-specific extensions to the
    standard GTFS specification.

## Quick start

### Requirements

- [uv](https://docs.astral.sh/uv/) with Python 3.13
- An [MBTA V3 API key](https://api-v3.mbta.com/)

### Setup

```bash
# Create a virtual environment
uv venv --python 3.13

# Install dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install

# Configure
cp config/template.json config/local.json
# Edit config/local.json with your MBTA V3 API key

# Run
uv run src/gobble.py
```

Output will be in `data/` in your current working directory.

### Running with Docker

```bash
docker build -t gobble -f Containerfile .
docker run \
    -v ./config/local.json:/app/config/local.json:z \
    -v ./data:/app/data:z \
    gobble:latest
```

## Support TransitMatters

If you've found this app helpful or interesting, please consider [donating](https://transitmatters.org/donate) to TransitMatters to help support our mission to provide data-driven advocacy for a more reliable, sustainable, and equitable transit system in Metropolitan Boston.
