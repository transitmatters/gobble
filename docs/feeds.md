# GTFS-RT Feed Status

This document tracks the status of GTFS-RT feeds configured in gobble, including authentication requirements and data support.

### MBTA

- **Mode**: SSE API (Server-Sent Events)
- **Feed URL**: MBTA V3 Streaming API
- **Authentication**: API key required (v3_api_key)
- **Mobility Database ID**: N/A
- **Routes Module**: [mbta_routes.py](../src/agencies/mbta_routes.py)
- **Notes**: Default mode for gobble; uses MBTA-specific streaming API

### Caltrain

- **Mode**: GTFS-RT
- **Feed URL**: `http://api.511.org/transit/vehiclepositions?agency=CT`
- **Authentication**: Query parameter (`api_key`)
- **Mobility Database ID**: mdb-54
- **Routes Module**: [caltrain_routes.py](../src/agencies/caltrain_routes.py)
- **Notes**: Requires 511.org API key

### Metra (Chicago)

- **Mode**: GTFS-RT
- **Feed URL**: `https://gtfspublic.metrarr.com/gtfs/public/positions`
- **Authentication**: None
- **Mobility Database ID**: mdb-2854
- **Routes Module**: [metra_routes.py](../src/agencies/metra_routes.py)
- **Notes**: Current static GTFS has spaces before the header names which causes issues. 

### MARTA Bus (Atlanta)

- **Mode**: GTFS-RT
- **Feed URL**: `https://gtfs-rt.itsmarta.com/TMGTFSRealTimeWebService/vehicle/vehiclepositions.pb`
- **Authentication**: Header (`api_key`)
- **Mobility Database ID**: mdb-368
- **Routes Module**: [marta_routes.py](../src/agencies/marta_routes.py)

### SEPTA Bus (Philadelphia)

- **Mode**: GTFS-RT
- **Feed URL**: `https://www3.septa.org/gtfsrt/septa-pa-us/Vehicle/rtVehiclePosition.pb`
- **Authentication**: None
- **Mobility Database ID**: mdb-502
- **Routes Module**: [septa_bus_routes.py](../src/agencies/septa_bus_routes.py)
- **Notes**: Open access feed

### SEPTA Regional Rail

- **Mode**: GTFS-RT
- **Feed URL**: `https://www3.septa.org/gtfsrt/septarail-pa-us/Vehicle/rtVehiclePosition.pb`
- **Authentication**: None
- **Mobility Database ID**: mdb-503
- **Routes Module**: [septa_rr_routes.py](../src/agencies/septa_rr_routes.py)

### WMATA Rail (Washington DC Metro)

- **Mode**: GTFS-RT
- **Feed URL**: `https://api.wmata.com/gtfs/rail-gtfsrt-vehiclepositions.pb`
- **Authentication**: Header (`api_key`)
- **Mobility Database ID**: mdb-1847
- **Routes Module**: [wmata_rail_routes.py](../src/agencies/wmata_rail_routes.py)

### WMATA Bus

- **Mode**: GTFS-RT
- **Feed URL**: `https://api.wmata.com/gtfs/bus-gtfsrt-vehiclepositions.pb`
- **Authentication**: Header (`api_key`)
- **Mobility Database ID**: mdb-1846
- **Routes Module**: [wmata_bus_routes.py](../src/agencies/wmata_bus_routes.py)

### WeGo Star (Nashville)

- **Mode**: GTFS-RT
- **Feed URL**: `http://transitdata.nashvillemta.org/TMGTFSRealTimeWebService/vehicle/vehiclepositions.pb`
- **Authentication**: None
- **Mobility Database ID**: Unknown
- **Routes Module**: [wegostar_routes.py](../src/agencies/wegostar_routes.py)
- **Notes**: Open access feed; MDB ID not yet determined

### TriMet (Portland)

- **Mode**: GTFS-RT
- **Feed URL**: `http://developer.trimet.org/ws/V1/VehiclePositions`
- **Authentication**: Query parameter (`appID`)
- **Mobility Database ID**: mdb-247
- **Routes Module**: Not setup yet. 
- **Notes**: Requires TriMet developer app ID

### King County Metro (Seattle)

- **Mode**: GTFS-RT
- **Feed URL**: `https://s3.amazonaws.com/kcm-alerts-realtime-prod/vehiclepositions.pb`
- **Authentication**: None
- **Mobility Database ID**: mdb-1847
- **Routes Module**: [kingcountymetro_routes.py](../src/agencies/kingcountymetro_routes.py)

### Denver RTD

- **Mode**: GTFS-RT
- **Feed URL**: `https://open-data.rtd-denver.com/files/gtfs-rt/rtd/VehiclePosition.pb`
- **Authentication**: None
- **Mobility Database ID**: mdb-178
- **Routes Module**: [denver_rtd_routes.py](../src/agencies/denver_rtd_routes.py)

### CTdot (Connecticut)

- **Mode**: GTFS-RT
- **Feed URL**: `https://cttprdtmgtfs.ctttrpcloud.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb`
- **Authentication**: None
- **Mobility Database ID**: tld-4436
- **Routes Module**: [ctdot_routes.py](../src/agencies/ctdot_routes.py)

### PVTA (Pioneer Valley)

- **Mode**: GTFS-RT
- **Feed URL**: `https://api.goswift.ly/real-time/pioneer-valley-pvta/gtfs-rt-vehicle-positions`
- **Authentication**: None
- **Mobility Database ID**: "mdb-2416"
- **Routes Module**: Not Set up yet
