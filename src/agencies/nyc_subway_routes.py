"""
NYC_SUBWAY route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> nyc_subway
"""

BUS_STOPS = {}

# NYC_SUBWAY Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# NYC_SUBWAY Commuter Rail/Regional Rail lines
ROUTES_CR = {"SI"}

# NYC_SUBWAY Rapid Transit routes
ROUTES_RAPID = {
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "6X",
    "7X",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "FS",
    "FX",
    "G",
    "GS",
    "H",
    "J",
    "L",
    "M",
    "N",
    "Q",
    "R",
    "W",
    "Z",
}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
