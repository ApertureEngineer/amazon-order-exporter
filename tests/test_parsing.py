from datetime import date

from amazon_order_exporter.parsing import parse_date


def test_parse_german_numeric_date() -> None:
    assert parse_date("14.04.2025") == date(2025, 4, 14)


def test_parse_german_month_date() -> None:
    assert parse_date("14. April 2025") == date(2025, 4, 14)


def test_parse_english_date() -> None:
    assert parse_date("April 14, 2025") == date(2025, 4, 14)
