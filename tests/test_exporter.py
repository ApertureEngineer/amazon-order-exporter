from datetime import date

from amazon_order_exporter.exporter import (
    _prepare_items_df,
    _prepare_orders_df,
    _shorten_item_title,
    _shorten_product_url,
)
from amazon_order_exporter.models import ItemRecord, OrderRecord


def test_shorten_product_url_uses_canonical_dp_url() -> None:
    assert (
        _shorten_product_url(
            "https://www.amazon.de/dp/B077XHDRNM?ref_=ppx_hzod_title_dt_b_fed_asin_title_0_0"
        )
        == "https://www.amazon.de/dp/B077XHDRNM"
    )
    assert (
        _shorten_product_url("https://www.amazon.de/gp/product/B09YM3V7NX?pd_rd_w=abc&ref_=x")
        == "https://www.amazon.de/dp/B09YM3V7NX"
    )


def test_shorten_item_title_keeps_recognizable_product_name() -> None:
    assert (
        _shorten_item_title(
            "Anker USB 4 Kabel 100cm, Unterst\u00fctzt 8K HD Display, "
            "40 Gbit/s Datentransfer, 240W USB C auf USB C Ladekabel"
        )
        == "Anker USB 4 Kabel"
    )
    assert (
        _shorten_item_title(
            "Beats Fit Pro \u2013 Komplett kabellose In-Ear Kopfh\u00f6rer \u2013 "
            "Aktives Noise-Cancelling, Kompatibel mit Apple & Android"
        )
        == "Beats Fit Pro"
    )
    assert (
        _shorten_item_title("CSL - USB C Kabel, 100W 2m PD 5A Schnellladekabel")
        == "CSL USB C Kabel"
    )


def test_prepare_orders_df_shortens_order_urls() -> None:
    orders_df = _prepare_orders_df(
        [
            OrderRecord(
                order_id="028-5408935-2527558",
                order_date_text="2. Dezember 2024",
                order_date=date(2024, 12, 2),
                order_total_text="13,90 EUR",
                status_text=None,
                detail_url=(
                    "https://www.amazon.de/your-orders/order-details?"
                    "orderID=028-5408935-2527558&ref=ppx_yo2ov_dt_b_fed_order_details"
                ),
                order_url=(
                    "https://www.amazon.de/your-orders/pop?ref=ppx_yo2ov_dt_b_pop&"
                    "orderId=028-5408935-2527558&lineItemId=x&shipmentId=y&packageId=1&asin=B077XHDRNM"
                ),
                page_no=1,
                raw_text="raw",
            )
        ]
    )

    assert orders_df.loc[0, "detail_url"] == (
        "https://www.amazon.de/your-orders/order-details?orderID=028-5408935-2527558"
    )
    assert orders_df.loc[0, "order_url"] == (
        "https://www.amazon.de/your-orders/pop?orderId=028-5408935-2527558"
    )


def test_prepare_items_df_adds_short_title_and_shortens_product_url() -> None:
    items_df = _prepare_items_df(
        [
            ItemRecord(
                order_id="028-5408935-2527558",
                order_date=date(2024, 12, 2),
                item_title=(
                    "Finish Quantum Infinity Shine Sp\u00fclmaschinentabs - "
                    "Geschirrsp\u00fcltabs f\u00fcr Tiefenreinigung, Sparpack mit 83 Tabs"
                ),
                product_url="https://www.amazon.de/dp/B09PYLZSQX?ref_=ppx_hzod_title_dt_b_fed_asin_title_0_0",
                source="order_history",
            )
        ]
    )

    assert list(items_df.columns[:5]) == [
        "order_id",
        "order_date",
        "item_title",
        "item_title_short",
        "product_url",
    ]
    assert items_df.loc[0, "item_title_short"] == "Finish Quantum Infinity Shine Sp\u00fclmaschinentabs"
    assert items_df.loc[0, "product_url"] == "https://www.amazon.de/dp/B09PYLZSQX"


def test_prepare_items_df_empty_output_has_short_title_column() -> None:
    items_df = _prepare_items_df([])

    assert "item_title_short" in items_df.columns
    assert items_df.empty
