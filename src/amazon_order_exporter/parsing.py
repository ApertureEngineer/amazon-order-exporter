from __future__ import annotations

import re
from datetime import date, datetime

ORDER_ID_RE = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")
DATE_PATTERNS = [
    re.compile(r"BESTELLUNG AUFGEGEBEN\s+([0-9]{1,2}\.\s*[A-Za-zÄÖÜäöü]+\s*[0-9]{4})", re.IGNORECASE),
    re.compile(r"Bestellt am\s+([0-9]{1,2}\.\s*[A-Za-zÄÖÜäöü]+\s*[0-9]{4})", re.IGNORECASE),
    re.compile(r"Bestellung aufgegeben am\s+([0-9]{1,2}\.\s*[A-Za-zÄÖÜäöü]+\s*[0-9]{4})", re.IGNORECASE),
    re.compile(r"Order placed\s+([A-Za-z]+\s+[0-9]{1,2},\s*[0-9]{4})", re.IGNORECASE),
    re.compile(r"Bestellt am\s+([0-9]{1,2}\.\s*[0-9]{1,2}\.\s*[0-9]{4})", re.IGNORECASE),
    re.compile(r"Order placed\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", re.IGNORECASE),
]
TOTAL_PATTERNS = [
    re.compile(r"SUMME\s*[:]?\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}\s*€)", re.IGNORECASE),
    re.compile(r"Gesamtsumme\s*[:]?\s*([0-9\.,]+\s*€)", re.IGNORECASE),
    re.compile(r"Order total\s*[:]?\s*([€$£]?\s*[0-9\.,]+)", re.IGNORECASE),
]
STATUS_PATTERNS = [
    re.compile(r"(Geliefert[^\n]*|Zugestellt[^\n]*|Unterwegs[^\n]*|Nicht zugestellt[^\n]*|Storniert[^\n]*)", re.IGNORECASE),
    re.compile(r"(Delivered[^\n]*|Arriving[^\n]*|Not yet shipped[^\n]*|Cancelled[^\n]*)", re.IGNORECASE),
]

GERMAN_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def find_first(patterns: list[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return normalize_whitespace(match.group(1))
    return None


def parse_order_date_text(text: str) -> str | None:
    return find_first(DATE_PATTERNS, text)


def parse_order_total_text(text: str) -> str | None:
    return find_first(TOTAL_PATTERNS, text)


def parse_status_text(text: str) -> str | None:
    return find_first(STATUS_PATTERNS, text)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None

    value = normalize_whitespace(value)

    for fmt in ("%d.%m.%Y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    german_match = re.match(r"([0-9]{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s*([0-9]{4})", value)
    if german_match:
        day = int(german_match.group(1))
        month_name = german_match.group(2).lower().replace("ü", "ue") if german_match.group(2).lower() == "märz" else german_match.group(2).lower()
        month_name = month_name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        month = GERMAN_MONTHS.get(month_name)
        if month:
            year = int(german_match.group(3))
            return date(year, month, day)

    return None


def in_range(order_date: date | None, date_from: date | None, date_to: date | None) -> bool:
    if order_date is None:
        return True
    if date_from and order_date < date_from:
        return False
    if date_to and order_date > date_to:
        return False
    return True
