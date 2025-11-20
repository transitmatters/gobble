"""SEPTA Regional Rail (Southeastern Pennsylvania Transportation Authority) route constants"""

BUS_STOPS = {}

# SEPTA Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# SEPTA Regional Rail lines
ROUTES_CR = {
    "AIR",
    "WAR",
    "WIL",
    "MED",
    "WTR",
    "LAN",
    "PAO",
    "CYN",
    "NOR",
    "Trenton",
    "CHE",
    "CHW",
    "FOX",
}

ROUTES_RAPID = {}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
