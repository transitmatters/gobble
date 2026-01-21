from datetime import date, datetime
from unittest.mock import patch
from util import (
    EASTERN_TIME,
    output_dir_path,
    service_date,
    to_dateint,
    get_current_service_date,
    service_date_iso8601,
)
import util


class TestUtil:
    def test_service_date(self):
        assert service_date(datetime(2023, 12, 15, 3, 0, 0)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 5, 45, 0)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 7, 15, 0)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 23, 59, 59)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 16, 0, 0, 0)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 16, 2, 59, 59)) == date(2023, 12, 15)

    def test_localized_datetime(self):
        assert service_date(datetime(2023, 12, 15, 3, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 5, 45, 0, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 7, 15, 0, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 15, 23, 59, 59, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 16, 0, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)
        assert service_date(datetime(2023, 12, 16, 2, 59, 59, tzinfo=EASTERN_TIME)) == date(2023, 12, 15)

    def test_edt_vs_est_datetimes(self):
        assert service_date(datetime(2023, 11, 5, 23, 59, 59, tzinfo=EASTERN_TIME)) == date(2023, 11, 5)
        assert service_date(datetime(2023, 11, 6, 0, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 11, 5)
        assert service_date(datetime(2023, 11, 6, 1, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 11, 5)
        assert service_date(datetime(2023, 11, 6, 2, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 11, 5)
        # 3am EST is 4am EDT
        assert service_date(datetime(2023, 11, 6, 3, 0, 0, tzinfo=EASTERN_TIME)) == date(2023, 11, 6)

    def test_output_dir_path_cr(self):
        # commuter rail uses _ as delimiter
        day_to_test = datetime(2024, 8, 7, 4)
        expected_suffix = f"/Year={day_to_test.year}/Month={day_to_test.month}/Day={day_to_test.day}"

        # Use MBTA CR route
        cr_route = "CR-Fairmount"
        cr_stop = output_dir_path(cr_route, "1", "DB-2205-01", day_to_test)

        # Verify structure
        assert cr_stop.startswith("daily-cr-data/")
        assert cr_stop.endswith(expected_suffix)
        assert "_1_DB-2205-01" in cr_stop

    def test_output_dir_path_rapid(self):
        # rapid transit doesn't need to split by direction / line
        day_to_test = datetime(2024, 8, 7, 4)
        expected_suffix = f"/Year={day_to_test.year}/Month={day_to_test.month}/Day={day_to_test.day}"

        # Use MBTA rapid route
        rapid_stop = output_dir_path("Red", "0", "68", day_to_test)
        assert rapid_stop == f"daily-rapid-data/68{expected_suffix}"

    def test_output_dir_path_bus(self):
        # bus doesn't have underscore but data is split
        day_to_test = datetime(2024, 8, 7, 4)
        expected_suffix = f"/Year={day_to_test.year}/Month={day_to_test.month}/Day={day_to_test.day}"

        bus_stop = output_dir_path("1", "0", "84", day_to_test)
        assert bus_stop == f"daily-bus-data/1-0-84{expected_suffix}"

    def test_to_date_int(self):
        assert to_dateint(date(2024, 8, 19)) == 20240819

    def test_get_current_service_date_caching(self):
        """Test that get_current_service_date() caches results per hour"""
        # Reset cache
        util._service_date_cache = None
        util._cache_hour = None

        # Mock datetime.now to return a specific time
        with patch("util.datetime") as mock_datetime:
            # First call at 10am
            mock_now_10am = datetime(2024, 8, 19, 10, 30, 0, tzinfo=EASTERN_TIME)
            mock_datetime.now.return_value = mock_now_10am
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result1 = get_current_service_date()
            assert result1 == date(2024, 8, 19)
            assert util._cache_hour == 10
            assert util._service_date_cache == date(2024, 8, 19)

            # Second call at same hour (should use cache)
            mock_now_10am_later = datetime(2024, 8, 19, 10, 45, 0, tzinfo=EASTERN_TIME)
            mock_datetime.now.return_value = mock_now_10am_later

            result2 = get_current_service_date()
            assert result2 == date(2024, 8, 19)
            # Cache should still be from 10am
            assert util._cache_hour == 10

            # Third call at different hour (should refresh cache)
            mock_now_11am = datetime(2024, 8, 19, 11, 15, 0, tzinfo=EASTERN_TIME)
            mock_datetime.now.return_value = mock_now_11am

            result3 = get_current_service_date()
            assert result3 == date(2024, 8, 19)
            # Cache should be updated to 11am
            assert util._cache_hour == 11

    def test_get_current_service_date_early_morning(self):
        """Test that get_current_service_date() handles early morning correctly"""
        # Reset cache
        util._service_date_cache = None
        util._cache_hour = None

        with patch("util.datetime") as mock_datetime:
            # Call at 2am (should return previous day)
            mock_now_2am = datetime(2024, 8, 20, 2, 30, 0, tzinfo=EASTERN_TIME)
            mock_datetime.now.return_value = mock_now_2am
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_current_service_date()
            assert result == date(2024, 8, 19)  # Previous day
            assert util._cache_hour == 2

    def test_service_date_iso8601(self):
        """Test service_date_iso8601 converts datetime to ISO format date"""
        ts = datetime(2024, 8, 19, 15, 30, 0)
        result = service_date_iso8601(ts)
        assert result == "2024-08-19"

        # Test early morning hours (should return previous day)
        ts_early = datetime(2024, 8, 20, 2, 30, 0)
        result_early = service_date_iso8601(ts_early)
        assert result_early == "2024-08-19"

        # Test boundary at 3am
        ts_boundary = datetime(2024, 8, 20, 3, 0, 0)
        result_boundary = service_date_iso8601(ts_boundary)
        assert result_boundary == "2024-08-20"
