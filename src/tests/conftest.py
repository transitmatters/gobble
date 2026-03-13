import pytest
import importlib

# Import fixtures from separate fixture modules


# MBTA-only configuration (removed agency parametrization)
MBTA_CONFIG = {
    "module": "agencies.mbta_routes",
    "sample_routes_cr": {"CR-Fairmount", "CR-Worcester"},
    "sample_routes_rapid": {"Red", "Orange"},
    "sample_routes_bus": {"1", "4"},
    "has_rapid_transit": True,
    "has_bus_routes": True,
}

# Import MBTA routes module
_mbta_module = importlib.import_module(MBTA_CONFIG["module"])


@pytest.fixture(scope="module")
def mock_agency_constants(monkeypatch):
    """
    Mock the constants module with MBTA-specific routes.
    Patches all constants that depend on the current agency.

    Module-scoped to avoid repeated monkeypatching overhead.
    """
    # Patch constants module with MBTA data
    import constants
    import util

    monkeypatch.setattr(constants, "AGENCY", "mbta")
    monkeypatch.setattr(constants, "BUS_STOPS", _mbta_module.BUS_STOPS)
    monkeypatch.setattr(constants, "ROUTES_BUS", _mbta_module.ROUTES_BUS)
    monkeypatch.setattr(constants, "ROUTES_CR", _mbta_module.ROUTES_CR)
    monkeypatch.setattr(constants, "ROUTES_RAPID", _mbta_module.ROUTES_RAPID)
    monkeypatch.setattr(constants, "ALL_ROUTES", _mbta_module.ALL_ROUTES)

    # Also patch the util module since it imported these at module load time
    monkeypatch.setattr(util, "ROUTES_CR", _mbta_module.ROUTES_CR)
    monkeypatch.setattr(util, "ROUTES_RAPID", _mbta_module.ROUTES_RAPID)

    return "mbta", MBTA_CONFIG


# ============================================================================
# EventSource Fixtures
# ============================================================================
# GTFS-RT and SSE specific fixtures are now in separate files:
# - tests/fixtures/gtfs_rt_fixtures.py
# - tests/fixtures/sse_fixtures.py
#
# Import them in your tests or configure pytest.ini to auto-load them.
