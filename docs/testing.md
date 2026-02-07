# Testing

Gobble uses [pytest](https://docs.pytest.org/) as its testing framework. All tests live in `src/tests/` and mirror the structure of the source modules.

## Running tests

```bash
# Run all unit tests
uv run pytest

# Run with coverage
uv run coverage run -m pytest
uv run coverage report

# Generate an HTML coverage report
uv run coverage html
# then open htmlcov/index.html

# Run a specific test file
uv run pytest src/tests/test_event.py

# Run a specific test class or method
uv run pytest src/tests/test_event.py::TestGetStopName
uv run pytest src/tests/test_event.py::TestGetStopName::test_get_stop_name_found

# Run with verbose output
uv run pytest -v
```

## Test markers

Tests can be tagged with [pytest markers](https://docs.pytest.org/en/stable/how.html#marking-test-functions-and-selecting-them-for-a-run). The following custom markers are defined in `pytest.ini`:

| Marker        | Purpose                                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `integration` | Tests that use real GTFS sample data from `src/tests/sample_data/`. These are slower and depend on file I/O. |

```bash
# Skip integration tests
uv run pytest -m "not integration"

# Run only integration tests
uv run pytest -m integration
```

## Test details

Each source module has a corresponding test file. The sections below describe what every test verifies.

### `test_gobble.py` — SSE client and main entry point

**TestConnect** — SSE connection establishment

| Test                        | Verifies                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `test_connect_basic`        | Constructs correct MBTA API URL, sets streaming headers (`Accept: text/event-stream`), and enables `stream=True` |
| `test_connect_single_route` | URL contains the correct `filter[route]=` parameter for a single route                                           |

**TestProcessEvents** — Event loop dispatching

| Test                                        | Verifies                                                                                 |
| ------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `test_process_events_handles_update_events` | `update` SSE events are forwarded to `process_event` (one call per event)                |
| `test_process_events_handles_reset_events`  | `reset` SSE events (JSON arrays) are unpacked and each item forwarded to `process_event` |
| `test_process_events_handles_add_events`    | `add` SSE events are processed the same way as `update` events                           |

**TestClientThread** — Reconnection and error handling

| Test                                    | Verifies                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------ |
| `test_client_thread_creates_connection` | Creates an SSE connection, wraps it in `SSEClient`, and calls `process_events` |
| `test_client_thread_retries_on_error`   | Reconnects automatically after a `ChunkedEncodingError`                        |
| `test_log_chunk_error`                  | Logs `ChunkedEncodingError` and generic exceptions with appropriate messages   |

---

### `test_event.py` — Event detection and enrichment pipeline

**TestGetStopName** — Stop name lookups from GTFS stops DataFrame

| Test                                 | Verifies                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------- |
| `test_get_stop_name_found`           | Returns the human-readable stop name when `stop_id` exists in the DataFrame      |
| `test_get_stop_name_not_found`       | Falls back to returning the raw `stop_id` string when it is not in the DataFrame |
| `test_get_stop_name_empty_dataframe` | Falls back to `stop_id` when the DataFrame is empty                              |

**TestArrOrDepEvent** — Arrival/departure state machine transitions

| Test                                         | Verifies                                                                                      |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `test_departure_event_new_stop`              | `IN_TRANSIT_TO` with an increased stop sequence after an `ARR` produces a departure           |
| `test_arrival_event_stopped_after_departure` | `STOPPED_AT` at a new stop after a `DEP` produces both a departure and an arrival             |
| `test_no_event_same_stop`                    | Staying `STOPPED_AT` at the same stop and sequence produces no event                          |
| `test_departure_with_stopped_at_status`      | `STOPPED_AT` at a new stop after an `ARR` (not `DEP`) produces a departure but not an arrival |

**TestReduceUpdateEvent** — Parsing raw MBTA API updates into internal tuples

| Test                                                     | Verifies                                                                                         |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `test_reduce_update_event_basic`                         | Extracts all fields (status, stop, route, trip, vehicle label, timestamps) from a minimal update |
| `test_reduce_update_event_with_carriages`                | Multi-carriage consists are joined with `\|` and per-car occupancy is preserved                  |
| `test_reduce_update_event_carriages_with_null_occupancy` | Carriages with `null` occupancy produce `None` for occupancy fields                              |
| `test_reduce_update_event_missing_stop`                  | `{"data": None}` in the stop relationship produces `stop_id = None`                              |
| `test_reduce_update_event_malformed_stop`                | Completely missing stop relationship (`None`) produces `stop_id = None`                          |
| `test_reduce_update_event_incoming_at_status`            | `INCOMING_AT` status maps to event type `ARR`                                                    |

**TestEnrichEvent** — GTFS schedule enrichment

| Test                | Verifies                                                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_enrich_event` | Fetches trips and stop_times by route, calls `add_gtfs_headways`, and returns an enriched dict with `scheduled_headway` and `scheduled_tt` |

**TestProcessEvent** — Full event processing pipeline

| Test                                          | Verifies                                                                                           |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `test_process_event_first_departure`          | A departure event fetches GTFS data, enriches the event, writes it to disk, and updates trip state |
| `test_process_event_skips_event_with_no_stop` | Events with a missing `stop_id` are silently skipped (no disk write, no GTFS fetch)                |
| `test_process_event_filters_bus_stops`        | Bus events are only written for stops listed in `constants.BUS_STOPS`                              |
| `test_process_event_no_write_for_non_event`   | No disk write occurs when the vehicle is still at the same stop and sequence                       |
| `test_process_event_first_time_seeing_trip`   | First sighting of a trip (no prior state) sets initial trip state without writing an event         |

**TestEventTypeMap** — Status-to-event-type constant

| Test                                        | Verifies                                                                                    |
| ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `test_event_type_map_has_expected_mappings` | `IN_TRANSIT_TO` → `DEP`, `STOPPED_AT` → `ARR`, `INCOMING_AT` → `ARR`, and exactly 3 entries |

---

### `test_gtfs.py` — GTFS archive and headway calculations

**TestGTFS** — Schedule matching and headway computation

| Test                                      | Verifies                                                                                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `test_add_gtfs_headways_batch`            | `batch_add_gtfs_headways` matches on-time, early, very-late, and very-early arrivals to the correct scheduled trip and computes headways |
| `test_add_gtfs_headways`                  | `add_gtfs_headways` produces the same results as the batch version for on-time, early, very-late, and very-early cases                   |
| `test_get_gtfs_archive_day_is_feed`       | _(integration)_ When the requested date is the feed start date, returns the archive directory named after that date                      |
| `test_get_gtfs_archive_day_not_feed`      | _(integration)_ When the requested date falls mid-feed, returns the archive directory named after the feed start date                    |
| `test_read_gtfs_date_exists_feed_is_read` | _(integration)_ Reads a real GTFS archive and verifies Orange Line termini, Red Line stop data, and Route 1 bus trips to Harvard         |

---

### `test_trip_state.py` — Trip state tracking and persistence

**TestTripStatePerformance** — Hot-path efficiency

| Test                                                     | Verifies                                                                            |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `test_get_trip_state_does_not_call_expensive_operations` | `get_trip_state` never triggers cleanup or file writes (keeping the read path fast) |

**TestTripStateCleanup** — Stale state removal

| Test                                    | Verifies                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------- |
| `test_cleanup_removes_stale_trips`      | Trips older than 5 hours are removed; recent trips are kept                |
| `test_overnight_purge_clears_all_trips` | A service date change clears all trips and updates the stored service date |

**TestTripStateFileIO** — File write behavior

| Test                              | Verifies                                                                               |
| --------------------------------- | -------------------------------------------------------------------------------------- |
| `test_set_trip_state_writes_once` | `set_trip_state` writes the state file exactly once per call (after cleanup completes) |

**TestTripStateIntegration** — Realistic workflow

| Test                      | Verifies                                                                                                                               |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `test_realistic_workflow` | Adding 10 trips over a simulated time range, then verifying recent trips are accessible while old ones (>5 hours) have been cleaned up |

**TestTripStateFilePersistence** — File round-tripping

| Test                                      | Verifies                                                                                                |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `test_file_updated_after_cleanup`         | After cleanup, the JSON file on disk contains only fresh and new trips (stale trips removed)            |
| `test_file_updated_after_overnight_purge` | After an overnight purge, the JSON file has the updated service date and only the newly added trip      |
| `test_file_can_be_read_back_correctly`    | Trip state written to disk can be loaded by a new `RouteTripsState` instance with matching field values |

---

### `test_disk.py` — CSV file writing

**TestWriteEvent** — `write_event` function

| Test                                                      | Verifies                                                                              |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `test_write_event_creates_new_file_with_header`           | First event creates a CSV file with the correct header row and one data row           |
| `test_write_event_appends_to_existing_file`               | Subsequent events for the same partition append to the existing file                  |
| `test_write_event_creates_partitioned_directories`        | Directory structure follows `daily-{mode}-data/{stop_id}/Year=.../Month=.../Day=.../` |
| `test_write_event_different_stops_create_different_files` | Events at different stops create separate CSV files                                   |
| `test_write_event_ignores_extra_fields`                   | Extra keys in the event dict are not written to the CSV                               |
| `test_write_event_handles_none_values`                    | `None` values are written as empty strings in the CSV                                 |

**TestDiskConstants** — Module constants

| Test                                       | Verifies                                                    |
| ------------------------------------------ | ----------------------------------------------------------- |
| `test_csv_filename`                        | `CSV_FILENAME` is `"events.csv"`                            |
| `test_csv_fields_contains_expected_fields` | `CSV_FIELDS` contains all 15 expected column names in order |
| `test_data_dir_is_pathlib_path`            | `DATA_DIR` is a `pathlib.Path` instance                     |
| `test_state_filename`                      | `STATE_FILENAME` is `"state.json"`                          |

---

### `test_s3_upload.py` — S3 upload

**TestCompressAndUploadFile** — Single file compression and upload

| Test                                            | Verifies                                                                                                                      |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `test_compress_and_upload_file_basic`           | Reads the file in binary, gzip-compresses it, uploads to `tm-mbta-performance` with correct content type and encoding headers |
| `test_compress_and_upload_file_correct_s3_path` | S3 key follows the format `Events-live/{relative_path}.gz`                                                                    |
| `test_compress_and_upload_empty_file`           | Empty files are still compressed and uploaded                                                                                 |
| `test_compress_and_upload_file_not_found`       | `FileNotFoundError` is raised and no upload is attempted                                                                      |

**TestUploadTodaysEventsToS3** — Daily upload orchestration

| Test                                          | Verifies                                                                                                                       |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `test_upload_todays_events_basic`             | Globs for today's CSV files and uploads each one                                                                               |
| `test_upload_todays_events_no_files`          | No uploads are attempted when glob returns no files                                                                            |
| `test_upload_todays_events_overnight_service` | Uses the MBTA service date (not calendar date) for the glob pattern — e.g., at 2 AM the service date is still the previous day |
| `test_upload_todays_events_upload_failure`    | S3 upload failures propagate as exceptions                                                                                     |
| `test_upload_todays_events_multiple_routes`   | Handles files across multiple routes, directions, and modes (rapid, bus, commuter rail)                                        |

**TestS3UploadConstants** — Module constants

| Test                                             | Verifies                                                                                                 |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `test_s3_bucket_name`                            | `S3_BUCKET` is `"tm-mbta-performance"`                                                                   |
| `test_s3_data_template`                          | `S3_DATA_TEMPLATE` is `"Events-live/{relative_path}.gz"`                                                 |
| `test_local_data_template_has_wildcard_patterns` | `LOCAL_DATA_TEMPLATE` contains glob wildcards for `daily-*`, `Year=`, `Month=`, `Day=`, and `events.csv` |

---

### `test_util.py` — Date/time and path utilities

#### TestUtil

| Test                                          | Verifies                                                                                       |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `test_service_date`                           | MBTA service date logic: times before 3 AM belong to the previous service day                  |
| `test_localized_datetime`                     | Same service date logic works with timezone-aware datetimes                                    |
| `test_edt_vs_est_datetimes`                   | Service date boundary is correct across the EDT/EST transition (3 AM EST = 4 AM EDT)           |
| `test_output_dir_path_cr`                     | Commuter rail paths use `daily-cr-data/` with underscore-separated route, direction, and stop  |
| `test_output_dir_path_rapid`                  | Rapid transit paths use `daily-rapid-data/{stop_id}/` (no route/direction in path)             |
| `test_output_dir_path_bus`                    | Bus paths use `daily-bus-data/{route}-{direction}-{stop}/`                                     |
| `test_to_date_int`                            | `to_dateint` converts a `date` to `YYYYMMDD` integer format                                    |
| `test_get_current_service_date_caching`       | Service date is cached per hour and refreshed when the hour changes                            |
| `test_get_current_service_date_early_morning` | At 2 AM, the cached service date is the previous calendar day                                  |
| `test_service_date_iso8601`                   | `service_date_iso8601` returns ISO 8601 date strings, respecting the 3 AM service day boundary |

---

### `test_timing.py` — Performance measurement decorator

#### TestMeasureTime

| Test                                     | Verifies                                                                                         |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `test_decorator_returns_function_result` | Decorated functions still return their original result                                           |
| `test_decorator_preserves_function_name` | `@wraps` preserves the original function's `__name__`                                            |
| `test_decorator_measures_execution_time` | Wall-clock time is captured (a 10 ms sleep takes at least 10 ms)                                 |
| `test_decorator_reports_statistics`      | With `report_frequency=1.0`, prints statistics including `last=`, `avg=`, `std=`, `min=`, `max=` |
| `test_decorator_limits_trail_length`     | Only the last N execution times are retained (controlled by `trail_length`)                      |
| `test_decorator_handles_kwargs`          | Decorated functions accept `*args` and `**kwargs` correctly                                      |
| `test_decorator_with_zero_frequency`     | With `report_frequency=0.0`, no statistics are ever printed                                      |
| `test_decorator_tracks_multiple_calls`   | Statistics accumulate correctly over multiple invocations                                        |

## Fixtures

Shared test fixtures are organized in `src/tests/fixtures/` by data source type:

### GTFS fixtures (`fixtures/gtfs_fixtures.py`)

| Fixture               | Scope    | Description                                                                   |
| --------------------- | -------- | ----------------------------------------------------------------------------- |
| `mock_stops_df`       | session  | Mock GTFS stops DataFrame with sample MBTA stations                           |
| `mock_trips_df`       | session  | Mock GTFS trips DataFrame with Red, Orange, and Blue line trips               |
| `mock_stop_times_df`  | session  | Mock stop_times DataFrame with arrival/departure times                        |
| `mock_gtfs_archive`   | function | A fresh `Mock(spec=GtfsArchive)` wired to the session-scoped DataFrames above |
| `empty_trips_df`      | session  | Empty DataFrame for tests expecting no trip data                              |
| `empty_stop_times_df` | session  | Empty DataFrame for tests expecting no stop_times data                        |

### SSE fixtures (`fixtures/sse_fixtures.py`)

| Fixture                       | Scope    | Description                                                 |
| ----------------------------- | -------- | ----------------------------------------------------------- |
| `sse_client_config`           | function | API key and URL for SSE client initialization               |
| `sample_sse_event`            | function | A single MBTA vehicle update event in the API's JSON format |
| `sample_event_reset_sequence` | function | A list of vehicle updates representing an SSE reset event   |

### Sample data (`sample_data/`)

Real (miniaturized) GTFS data files used by integration tests:

- `stops_times_mini.txt` — A small subset of GTFS `stop_times.txt`
- `trips_mini.txt` — A small subset of GTFS `trips.txt`

## Writing tests

### Conventions

- **One test file per source module** — name it `test_<module>.py`
- **Group related tests in classes** — e.g., `TestGetStopName` for the `get_stop_name` function
- **Google-style docstrings** on all test classes and methods
- **Use `unittest.mock`** (`patch`, `Mock`, `MagicMock`) to isolate units under test
- **Use `tmp_path`** (pytest built-in fixture) for tests that write to disk

### Adding a new test

1. Create or open the test file corresponding to the source module
2. Add a test class grouping related tests
3. Add docstrings explaining what each test verifies and why
4. If the test needs shared mock data, add a fixture to the appropriate file in `fixtures/`
5. If the test requires real GTFS files or is slow, mark it with `@pytest.mark.integration`

### Example

```python
class TestMyFeature:
    """Tests for the my_feature function in event.py."""

    def test_handles_normal_input(self):
        """Normal input should produce expected output."""
        result = my_feature("input")
        assert result == "expected"

    def test_handles_missing_data(self):
        """Missing data should return None rather than raising."""
        result = my_feature(None)
        assert result is None
```
