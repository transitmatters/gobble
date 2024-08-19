from datetime import date, datetime
from util import EASTERN_TIME, output_dir_path, service_date, to_dateint
from unittest import TestCase

class TestUtil(TestCase):
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

    def test_output_dir_path(self):
        # commuter rail uses _ as delimiter
        day_to_test = datetime(2024, 8, 7, 4)
        expected_suffix = f'/Year={day_to_test.year}/Month={day_to_test.month}/Day={day_to_test.day}'

        cr_stop = output_dir_path('CR-Fairmount', '1', 'DB-2205-01', day_to_test)
        assert cr_stop == f'daily-cr-data/CR-Fairmount_1_DB-2205-01{expected_suffix}'

        # no need to split rapid data by direction / line
        rapid_stop = output_dir_path('Red', '0', '68', day_to_test)
        assert rapid_stop == f'daily-rapid-data/68{expected_suffix}'

        # bus doesn't have underscore but data is split
        bus_stop = output_dir_path('1', '0', '84', day_to_test)
        assert bus_stop == f'daily-bus-data/1-0-84{expected_suffix}'

    def test_to_date_int(self):
        assert to_dateint(date(2024, 8, 19)) == 20240819


