#!/usr/bin/env python3
"""
Generate agency route files from GTFS Static data.

This script extracts routes and their associated stops from GTFS Static bundles
and generates Python files that can be imported by the constants module.

The generated files contain:
- BUS_STOPS: Dict mapping route IDs to sets of stop IDs
- ROUTES_BUS: Set of bus route IDs
- ROUTES_CR: Set of commuter rail route IDs
- ROUTES_RAPID: Set of rapid transit route IDs
- ALL_ROUTES: Union of all route sets

Usage:
    python generate_agency_routes.py <gtfs_zip_path> <output_agency_name> [options]

Examples:
    # Generate for MBTA from a GTFS zip file
    python generate_agency_routes.py data/mbta.zip mbta

    # Generate with custom route type mapping
    python generate_agency_routes.py data/caltrain.zip caltrain \\
        --route-types-bus 3 --route-types-cr 2 --route-types-rapid ""

    # Generate and specify output location
    python generate_agency_routes.py data/gtfs.zip agency_name \\
        --output-dir ./custom_output_dir
"""

import argparse
import csv
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Dict, Set, Tuple


class TrimmedDictReader(csv.DictReader):
    """CSV DictReader that strips whitespace from field names."""

    @property
    def fieldnames(self):
        return [name.strip() if name else name for name in super().fieldnames]


def get_zip_file_path(gtfs_zip: str) -> Path:
    """
    Get a Path to a GTFS zip file.

    If gtfs_zip is a URL, download it to a temporary file.
    Otherwise, treat it as a local file path.

    Returns the Path to the zip file.
    """
    if gtfs_zip.startswith(("http://", "https://")):
        print(f"Downloading GTFS from: {gtfs_zip}")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_path = Path(temp_file.name)
        temp_file.close()

        try:
            urllib.request.urlretrieve(gtfs_zip, temp_path)
            print(f"Downloaded to: {temp_path}")
            return temp_path
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            raise ValueError(f"Failed to download GTFS from {gtfs_zip}: {e}")
    else:
        return Path(gtfs_zip)


def extract_zip_files(zip_path: Path, *filenames: str) -> list[str]:
    """Extract multiple files from a zip archive and return their contents."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            results = []
            for filename in filenames:
                try:
                    results.append(zip_file.read(filename).decode("utf-8"))
                except KeyError:
                    raise FileNotFoundError(f"File '{filename}' not found in {zip_path}")
            return results
    except zipfile.BadZipFile:
        raise ValueError(f"Invalid zip file: {zip_path}")


def parse_routes_txt(content: str) -> Dict[str, Tuple[str, str]]:
    """
    Parse routes.txt from GTFS.

    Returns a dict mapping route_id -> (route_short_name, route_type).
    Route types: 0=tram, 1=subway, 2=rail, 3=bus, 4=ferry, 12=cable_car, etc.
    """
    routes = {}
    reader = TrimmedDictReader(StringIO(content))
    for row in reader:
        route_id = row.get("route_id", "").strip()
        route_type = row.get("route_type", "").strip()
        route_short_name = row.get("route_short_name", "").strip()
        if route_id:
            routes[route_id] = (route_short_name, route_type)
    return routes


def parse_trips_txt(content: str) -> Dict[str, str]:
    """
    Parse trips.txt from GTFS.

    Returns a dict mapping trip_id -> route_id.
    """
    trips = {}
    reader = TrimmedDictReader(StringIO(content))
    for row in reader:
        trip_id = row.get("trip_id", "").strip()
        route_id = row.get("route_id", "").strip()
        if trip_id and route_id:
            trips[trip_id] = route_id
    return trips


def build_route_stops(
    routes: Dict[str, Tuple[str, str]],
    trips: Dict[str, str],
    stop_times_content: str,
) -> Dict[str, Set[str]]:
    """
    Build mapping from route_id to set of stop_ids.

    Streams stop_times.txt to avoid loading the full trip->stops mapping into memory.
    """
    route_stops: Dict[str, Set[str]] = defaultdict(set)
    reader = TrimmedDictReader(StringIO(stop_times_content))
    for row in reader:
        trip_id = row.get("trip_id", "").strip()
        stop_id = row.get("stop_id", "").strip()
        if trip_id and stop_id:
            route_id = trips.get(trip_id)
            if route_id and route_id in routes:
                route_stops[route_id].add(stop_id)
    return dict(route_stops)


def _route_sort_key(x: str) -> tuple:
    return (int(x) if x.isdigit() else 999999, x)


def categorize_routes(
    routes: Dict[str, Tuple[str, str]],
    route_types_bus: Set[str],
    route_types_cr: Set[str],
    route_types_rapid: Set[str],
) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Categorize routes by their type (bus, commuter rail, rapid transit).

    Returns (routes_bus, routes_cr, routes_rapid).
    """
    routes_bus = set()
    routes_cr = set()
    routes_rapid = set()

    for route_id, (_, route_type) in routes.items():
        if route_type in route_types_rapid:
            routes_rapid.add(route_id)
        elif route_type in route_types_cr:
            routes_cr.add(route_id)
        elif route_type in route_types_bus:
            routes_bus.add(route_id)

    return routes_bus, routes_cr, routes_rapid


def format_python_dict(data: Dict[str, Set[str]]) -> str:
    """Format a dict of route_id -> set of stop_ids as a Python dict literal."""
    lines = ["{"]
    for route_id in sorted(data.keys(), key=_route_sort_key):
        stops = data[route_id]
        stops_str = "{" + ", ".join(f'"{s}"' for s in sorted(stops)) + "}"
        lines.append(f'    "{route_id}": {stops_str},')
    lines.append("}")
    return "\n".join(lines)


def format_python_set(data: Set[str]) -> str:
    """Format a set as a Python set literal."""
    if not data:
        return "set()"
    items = sorted(data, key=_route_sort_key)
    return "{" + ", ".join(f'"{item}"' for item in items) + "}"


def generate_agency_file(
    agency_name: str,
    route_stops: Dict[str, Set[str]],
    routes_bus: Set[str],
    routes_cr: Set[str],
    routes_rapid: Set[str],
) -> str:
    """Generate the Python code for an agency routes file."""
    bus_stops_filtered = {k: v for k, v in route_stops.items() if k in routes_bus}

    code = f'''"""
{agency_name.upper()} route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> {agency_name}
"""

BUS_STOPS = {format_python_dict(bus_stops_filtered)}

# {agency_name.upper()} Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# {agency_name.upper()} Commuter Rail/Regional Rail lines
ROUTES_CR = {format_python_set(routes_cr)}

# {agency_name.upper()} Rapid Transit routes
ROUTES_RAPID = {format_python_set(routes_rapid)}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
'''
    return code


def main():
    parser = argparse.ArgumentParser(
        description="Generate agency route files from GTFS Static data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "gtfs_zip",
        type=str,
        help="Path or URL to GTFS Static zip file (e.g., /path/to/file.zip or https://example.com/gtfs.zip)",
    )

    parser.add_argument("agency_name", help="Name of the agency (e.g., 'mbta', 'caltrain')")

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("src/agencies"),
        help="Output directory for generated file (default: src/agencies)",
    )

    parser.add_argument(
        "--route-types-bus",
        type=lambda x: set(x.split(",")),
        default={"3"},
        help="Comma-separated list of GTFS route_type values for bus (default: 3)",
    )

    parser.add_argument(
        "--route-types-cr",
        type=lambda x: set(x.split(",")) if x else set(),
        default={"2"},
        help="Comma-separated list of GTFS route_type values for commuter rail (default: 2)",
    )

    parser.add_argument(
        "--route-types-rapid",
        type=lambda x: set(x.split(",")) if x else set(),
        default={"0", "1"},
        help="Comma-separated list of GTFS route_type values for rapid transit (default: 0,1)",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Get the zip file path (download if URL, otherwise use local path)
    gtfs_zip_path = None
    try:
        gtfs_zip_path = get_zip_file_path(args.gtfs_zip)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not gtfs_zip_path.exists():
        print(f"Error: GTFS zip file not found: {gtfs_zip_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing GTFS file: {gtfs_zip_path}")

    try:
        print("Extracting GTFS data...")
        routes_content, trips_content, stop_times_content = extract_zip_files(
            gtfs_zip_path, "routes.txt", "trips.txt", "stop_times.txt"
        )

        print("Parsing routes...")
        routes = parse_routes_txt(routes_content)
        print(f"  Found {len(routes)} routes")

        print("Parsing trips...")
        trips = parse_trips_txt(trips_content)
        print(f"  Found {len(trips)} trips")

        print("Building stop mappings...")
        route_stops = build_route_stops(routes, trips, stop_times_content)
        print(f"  Built mappings for {len(route_stops)} routes")

        print("Categorizing routes...")
        routes_bus, routes_cr, routes_rapid = categorize_routes(
            routes,
            args.route_types_bus,
            args.route_types_cr,
            args.route_types_rapid,
        )
        print(f"  Bus routes: {len(routes_bus)}")
        print(f"  Commuter rail routes: {len(routes_cr)}")
        print(f"  Rapid transit routes: {len(routes_rapid)}")

        print("Generating Python file...")
        file_content = generate_agency_file(
            args.agency_name,
            route_stops,
            routes_bus,
            routes_cr,
            routes_rapid,
        )

        output_file = args.output_dir / f"{args.agency_name}_routes.py"
        output_file.write_text(file_content)
        print(f"\nSuccess! Generated: {output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up temporary file if it was downloaded from a URL
        if gtfs_zip_path and args.gtfs_zip.startswith(("http://", "https://")) and gtfs_zip_path.exists():
            gtfs_zip_path.unlink()
            print(f"Cleaned up temporary file: {gtfs_zip_path}")


if __name__ == "__main__":
    main()
