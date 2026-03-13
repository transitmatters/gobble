"""
SOUNDTRANSIT route constants.

Auto-generated from GTFS Static data. Do not manually edit.
Regenerate using: python generate_agency_routes.py <gtfs_zip> soundtransit
"""

BUS_STOPS = {
    "1-SHUTTLE": {
        "LS_N11_T1",
        "LS_N11_T2",
        "LS_N15_T1",
        "LS_N15_T2",
        "LS_N17_T1",
        "LS_N17_T2",
        "LS_N19_T1",
        "LS_N19_T2",
        "LS_N23_T1",
        "LS_N23_T2",
    },
}

# SOUNDTRANSIT Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# SOUNDTRANSIT Commuter Rail/Regional Rail lines
ROUTES_CR = {"SNDR_EV", "SNDR_TL"}

# SOUNDTRANSIT Rapid Transit routes
ROUTES_RAPID = {"100479", "2LINE", "TLINE"}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
