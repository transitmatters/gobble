"""CTDOT (Connecticut Department of Transportation) route constants"""

BUS_STOPS = {}

# CTDOT Bus routes
ROUTES_BUS = set(BUS_STOPS.keys())

# CTDOT Regional Rail lines
ROUTES_CR = {"HART"}

ROUTES_RAPID = {}


ALL_ROUTES = ROUTES_BUS.union(ROUTES_CR).union(ROUTES_RAPID)
