from datetime import date

from amazon_order_exporter.parsing import parse_date, parse_order_date_text, parse_order_total_text


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
