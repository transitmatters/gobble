"""
Route constants - dynamically loaded based on configured agency.

This module loads route constants (BUS_STOPS, ROUTES_BUS, ROUTES_CR, ROUTES_RAPID, ALL_ROUTES)
from agency-specific files based on the 'agency' setting in config/local.json.
Each set of constants correlates a GTFS Static, and GTFS-RT pair.
For example SEPTA maintains seperate GTFS bundles for Regional Rail and Bus/Trolley.

Supported agencies:
- mbta: Massachusetts Bay Transportation Authority
- septa_regionalrail: Southeastern Pennsylvania Transportation Authority Regional Rail
"""

import importlib
from config import CONFIG

# Determine which agency configuration to load
AGENCY = CONFIG.get("agency", "mbta").lower()


AGENCY_MODULES = {
    "mbta": "agencies.mbta_routes",
    "septa_regionalrail": "agencies.septa_rr_routes",
    "septa_bus": "agencies.septa_bus_routes",
    "ctdot": "agencies.ctdot_routes",
    "caltrain": "agencies.caltrain_routes",
    "denver_rtd": "agencies.denver_rtd_routes",
    "kingcountymetro": "agencies.kingcountymetro_routes",
    "wegostar": "agencies.wegostar_routes",
    "wmata_bus": "agencies.wmata_bus_routes",
    "wmata_rail": "agencies.wmata_rail_routes",
    "marta": "agencies.marta_routes",
    "lirr": "agencies.lirr_routes",
    "nyc_subway": "agencies.nyc_subway_routes",
    "stm_montreal_bus": "agencies.stm_montreal_routes",
    "pvta": "agencies.pvta_routes",
    "ripta": "agencies.ripta_routes",
    "metro_transit": "agencies.metro_transit_routes",
    "meva": "agencies.meva_routes",
    "cats": "agencies.cats_routes",
    "ttc": "agencies.ttc_routes",
}

if AGENCY not in AGENCY_MODULES:
    raise ValueError(
        f"Unknown agency '{AGENCY}'. Supported agencies: {list(AGENCY_MODULES)}."
    )

mod = importlib.import_module(AGENCY_MODULES[AGENCY])

BUS_STOPS = mod.BUS_STOPS
ROUTES_BUS = mod.ROUTES_BUS
ROUTES_CR = mod.ROUTES_CR
ROUTES_RAPID = mod.ROUTES_RAPID
ALL_ROUTES = mod.ALL_ROUTES
