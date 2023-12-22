from datetime import date, datetime
from util import EASTERN_TIME, service_date


def test_service_date():
    assert service_date(datetime(2023, 12, 15, 3, 0, 0)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 5, 45, 0)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 7, 15, 0)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 23, 59, 59)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 0, 0, 0)) == date(2023, 12, 14)
    assert service_date(datetime(2023, 12, 15, 2, 59, 59)) == date(2023, 12, 14)


def test_localized_datetime():
    assert service_date(datetime(2023, 12, 15, 3, 0, 0).astimezone(EASTERN_TIME)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 5, 45, 0).astimezone(EASTERN_TIME)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 7, 15, 0).astimezone(EASTERN_TIME)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 23, 59, 59).astimezone(EASTERN_TIME)) == date(2023, 12, 15)
    assert service_date(datetime(2023, 12, 15, 0, 0, 0).astimezone(EASTERN_TIME)) == date(2023, 12, 14)
    assert service_date(datetime(2023, 12, 15, 2, 59, 59).astimezone(EASTERN_TIME)) == date(2023, 12, 14)
