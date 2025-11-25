"""
LIRR route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> lirr
"""

BUS_STOPS = {
}

# LIRR Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# LIRR Commuter Rail/Regional Rail lines
ROUTES_CR = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"}

# LIRR Rapid Transit routes
ROUTES_RAPID = set()


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
