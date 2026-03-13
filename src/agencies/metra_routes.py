"""
METRA route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> metra
"""

BUS_STOPS = {}

# METRA Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# METRA Commuter Rail/Regional Rail lines
ROUTES_CR = {
    "BNSF",
    "HC",
    "MD-N",
    "MD-W",
    "ME",
    "NCS",
    "RI",
    "SWS",
    "UP-N",
    "UP-NW",
    "UP-W",
}

# METRA Rapid Transit routes
ROUTES_RAPID = set()


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
