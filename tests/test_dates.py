from datetime import date, timedelta

import pytest

from greentechhub_core.dates import fiscal_year, fiscal_year_bounds, fiscal_year_label

# fiscal_year


@pytest.mark.parametrize(
    ("d", "start_month", "expected"),
    [
        (date(2025, 6, 30), 7, 2024),  # the last day of FY 2024
        (date(2025, 7, 1), 7, 2025),  # the first day of FY 2025
        (date(2025, 1, 15), 7, 2024),
        (date(2025, 12, 31), 7, 2025),
        (date(2025, 3, 31), 4, 2024),  # an April start (e.g. the UK's)
        (date(2025, 4, 1), 4, 2025),
        (date(2025, 1, 1), 1, 2025),  # the calendar year
        (date(2025, 12, 31), 1, 2025),
    ],
)
def test_fiscal_year_is_the_year_it_starts_in(d, start_month, expected):
    assert fiscal_year(d, start_month) == expected


def test_fiscal_year_defaults_to_a_july_start():
    # PyFinBot's au_fiscal_year: FY N spans 1 Jul N to 30 Jun N+1.
    samples = {date(2024, 7, 1): 2024, date(2025, 6, 30): 2024, date(2024, 6, 30): 2023,
               date(2000, 1, 1): 1999, date(2026, 10, 3): 2026}
    for d, fy in samples.items():
        assert fiscal_year(d) == fy, d


# fiscal_year_bounds


@pytest.mark.parametrize(
    ("fy", "start_month", "bounds"),
    [
        (2024, 7, (date(2024, 7, 1), date(2025, 6, 30))),
        (2024, 4, (date(2024, 4, 1), date(2025, 3, 31))),
        (2024, 1, (date(2024, 1, 1), date(2024, 12, 31))),
        (2023, 3, (date(2023, 3, 1), date(2024, 2, 29))),  # a leap February
    ],
)
def test_fiscal_year_bounds_are_inclusive(fy, start_month, bounds):
    assert fiscal_year_bounds(fy, start_month) == bounds


@pytest.mark.parametrize("start_month", range(1, 13))
def test_bounds_round_trip_through_fiscal_year(start_month):
    start, end = fiscal_year_bounds(2024, start_month)
    assert fiscal_year(start, start_month) == fiscal_year(end, start_month) == 2024
    assert fiscal_year(start - timedelta(days=1), start_month) == 2023
    assert fiscal_year(end + timedelta(days=1), start_month) == 2025


# fiscal_year_label


@pytest.mark.parametrize(
    ("fy", "start_month", "label"),
    [(2024, 7, "2024–25"), (1999, 7, "1999–00"), (2009, 4, "2009–10"), (2024, 1, "2024")],
)
def test_fiscal_year_label(fy, start_month, label):
    assert fiscal_year_label(fy, start_month) == label


# start_month validation


@pytest.mark.parametrize("bad", [0, 13, -1])
def test_start_month_outside_1_to_12_raises(bad):
    with pytest.raises(ValueError, match="start_month"):
        fiscal_year(date(2025, 1, 1), bad)
    with pytest.raises(ValueError, match="start_month"):
        fiscal_year_bounds(2024, bad)
    with pytest.raises(ValueError, match="start_month"):
        fiscal_year_label(2024, bad)
