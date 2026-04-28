from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

from .models import ItemRecord, OrderRecord


ASIN_RE = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)
DETAIL_SPLIT_RE = re.compile(r"\s*(?:,|;|\||\s+[\u2013\u2014-]\s+)\s*")
TRAILING_DETAIL_RE = re.compile(
    r"\s+\b(?:f\u00fcr|for|kompatibel|compatible|unterst\u00fctzt|supports|mit|with|inkl\.?|inklusive|including)\b.*$",
    re.IGNORECASE,
)
TRAILING_SPEC_RE = re.compile(
    r"(?:\s+\d+(?:[.,]\d+)?\s?(?:cm|mm|m|kg|g|ml|l|w|gb|tb|st\u00fcck|pcs|pack))+$",
    re.IGNORECASE,
)
ORDER_QUERY_KEYS = ("orderID", "orderId", "orderid")
FALLBACK_QUERY_KEYS = ("asin", "ASIN")


class ExportPaths:
    def __init__(self, xlsx_path: Path):
        self.xlsx_path = xlsx_path
        self.orders_csv_path = xlsx_path.with_suffix(".orders.csv")
        self.items_csv_path = xlsx_path.with_suffix(".items.csv")


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        value = str(value)
    normalized = value.strip()
    return normalized or None


def _shorten_product_url(url: object) -> str | None:
    url = _clean_optional_text(url)
    if url is None:
        return None
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    asin = None
    for idx, part in enumerate(path_parts[:-1]):
        if part.lower() in {"dp", "product"} and ASIN_RE.fullmatch(path_parts[idx + 1]):
            asin = path_parts[idx + 1]
            break

    if asin and parsed.scheme and parsed.netloc:
        return urlunparse((parsed.scheme, parsed.netloc, f"/dp/{asin}", "", "", ""))

    return _shorten_url_query(url)


def _shorten_order_url(url: object) -> str | None:
    url = _clean_optional_text(url)
    if url is None:
        return None
    return _shorten_url_query(url, preferred_keys=ORDER_QUERY_KEYS, fallback_keys=FALLBACK_QUERY_KEYS)


def _shorten_url_query(
    url: str,
    preferred_keys: tuple[str, ...] = (),
    fallback_keys: tuple[str, ...] = (),
) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url

    query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
    keys_to_keep = preferred_keys
    if not any(key == pair_key for key in preferred_keys for pair_key, _ in query_pairs):
        keys_to_keep = fallback_keys

    if keys_to_keep:
        keep = [(key, value) for key, value in query_pairs if key in keys_to_keep]
    else:
        keep = [
            (key, value)
            for key, value in query_pairs
            if not key.lower().startswith(("ref", "pd_rd", "pf_rd")) and key.lower() not in {"qid", "tag"}
        ]

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(keep), ""))


def _shorten_item_title(title: object) -> str | None:
    title = _clean_optional_text(title)
    if title is None:
        return None

    normalized = " ".join(title.split())
    normalized = re.sub(r"\s*\([^)]*\)", "", normalized).strip()
    normalized = TRAILING_DETAIL_RE.sub("", normalized).strip()
    parts = [part.strip() for part in DETAIL_SPLIT_RE.split(normalized) if part.strip()]
    if not parts:
        return normalized[:80].strip()

    short_title = parts[0]
    if len(parts) > 1 and len(short_title) <= 5 and len(parts[1].split()) <= 5:
        short_title = f"{short_title} {parts[1]}"

    short_title = TRAILING_DETAIL_RE.sub("", short_title).strip()
    short_title = TRAILING_SPEC_RE.sub("", short_title).strip()
    words = short_title.split()
    if len(words) > 7:
        short_title = " ".join(words[:7])
    if len(short_title) > 80:
        short_title = short_title[:80].rsplit(" ", 1)[0].strip()
    return short_title or normalized[:80].strip()


def _prepare_orders_df(orders: list[OrderRecord]) -> pd.DataFrame:
    orders_df = pd.DataFrame([row.to_dict() for row in orders])
    if orders_df.empty:
        orders_df = pd.DataFrame(columns=[
            "order_id",
            "order_date_text",
            "order_date",
            "order_total_text",
            "status_text",
            "detail_url",
            "order_url",
            "page_no",
            "raw_text",
            "item_links",
        ])
    for column in ("detail_url", "order_url"):
        if column in orders_df.columns:
            orders_df[column] = orders_df[column].map(_shorten_order_url)
    return orders_df


def _prepare_items_df(items: list[ItemRecord]) -> pd.DataFrame:
    items_df = pd.DataFrame([row.to_dict() for row in items])
    if items_df.empty:
        items_df = pd.DataFrame(columns=[
            "order_id",
            "order_date",
            "item_title",
            "item_title_short",
            "product_url",
            "source",
            "item_price_text",
            "item_price_amount",
            "quantity_text",
            "order_total_text",
            "order_total_amount",
            "price_source",
        ])
    else:
        items_df["item_title_short"] = items_df["item_title"].map(_shorten_item_title)
        title_idx = items_df.columns.get_loc("item_title")
        columns = list(items_df.columns)
        columns.insert(title_idx + 1, columns.pop(columns.index("item_title_short")))
        items_df = items_df[columns]

    if "product_url" in items_df.columns:
        items_df["product_url"] = items_df["product_url"].map(_shorten_product_url)
    return items_df


def write_outputs(orders: list[OrderRecord], items: list[ItemRecord], output_path: Path) -> ExportPaths:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paths = ExportPaths(output_path)

    orders_df = _prepare_orders_df(orders)
    items_df = _prepare_items_df(items)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        orders_df.to_excel(writer, sheet_name="orders", index=False)
        items_df.to_excel(writer, sheet_name="items", index=False)

    orders_df.to_csv(paths.orders_csv_path, index=False, encoding="utf-8-sig")
    items_df.to_csv(paths.items_csv_path, index=False, encoding="utf-8-sig")

    return paths
