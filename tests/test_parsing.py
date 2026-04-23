from datetime import date

from amazon_order_exporter.parsing import (
    ORDER_ID_RE,
    in_range,
    parse_date,
    parse_money_amount,
    parse_order_date_text,
    parse_order_total_text,
)


def test_parse_german_numeric_date() -> None:
    assert parse_date("14.04.2025") == date(2025, 4, 14)


def test_parse_german_month_date() -> None:
    assert parse_date("14. April 2025") == date(2025, 4, 14)


def test_parse_english_date() -> None:
    assert parse_date("April 14, 2025") == date(2025, 4, 14)


def test_parse_german_umlaut_month_date() -> None:
    assert parse_date("14. März 2025") == date(2025, 3, 14)


def test_parse_invalid_date_returns_none() -> None:
    assert parse_date("not-a-date") is None


def test_parse_order_date_text_for_bestellung_aufgegeben() -> None:
    text = "Ihre Bestellung. Bestellung aufgegeben am 3. März 2025. Wird versandt."
    assert parse_order_date_text(text) == "3. März 2025"


def test_parse_order_date_text_for_bestellt_am_numeric() -> None:
    text = "Bestellt am 03. 03. 2025"
    assert parse_order_date_text(text) == "03. 03. 2025"


def test_parse_order_date_text_for_bestellung_aufgegeben_without_am() -> None:
    text = "BESTELLUNG AUFGEGEBEN 2. Dezember 2024 SUMME 13,90 €"
    assert parse_order_date_text(text) == "2. Dezember 2024"


def test_parse_order_total_text_for_summe() -> None:
    text = "BESTELLUNG AUFGEGEBEN 2. Dezember 2024 SUMME 1.213,90 €"
    assert parse_order_total_text(text) == "1.213,90 €"


def test_parse_money_amount_for_german_currency_text() -> None:
    assert parse_money_amount("1.213,90 EUR") == 1213.90
    assert parse_money_amount("66,70 EUR") == 66.70


def test_order_id_regex_matches_classic_and_digital_orders() -> None:
    assert ORDER_ID_RE.fullmatch("028-5408935-2527558")
    assert ORDER_ID_RE.fullmatch("D01-5862153-3736618")
    assert not ORDER_ID_RE.fullmatch("261-7744337-7172819-EXTRA")


def test_in_range_unknown_date_without_filter_is_included() -> None:
    assert in_range(None, None, None) is True


def test_in_range_unknown_date_with_filter_is_included_by_default() -> None:
    assert in_range(None, date(2024, 1, 1), date(2024, 12, 31)) is True


def test_in_range_unknown_date_with_filter_can_be_excluded() -> None:
    assert in_range(None, date(2024, 1, 1), date(2024, 12, 31), include_unknown_when_filtered=False) is False
