"""
WMATA_RAIL route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> wmata_rail
"""

BUS_STOPS = {
    "SHUTTLE": {"PF_E08_1", "PF_E09_C", "PF_E10_C"},
}

# WMATA_RAIL Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# WMATA_RAIL Commuter Rail/Regional Rail lines
ROUTES_CR = set()

# WMATA_RAIL Rapid Transit routes
ROUTES_RAPID = {"BLUE", "GREEN", "ORANGE", "RED", "SILVER", "YELLOW"}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
