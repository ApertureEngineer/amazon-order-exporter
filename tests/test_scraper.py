from datetime import date

from amazon_order_exporter.models import OrderRecord
from amazon_order_exporter.scraper import AmazonScraper, ScrapeConfig


class _FakeLocator:
    def __init__(self, text: str):
        self._text = text

    def inner_text(self) -> str:
        return self._text


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def locator(self, _selector: str) -> _FakeLocator:
        return _FakeLocator(self._text)

    def evaluate(self, _script: str) -> list[dict[str, str]]:
        return []

    def close(self) -> None:
        return None


class _FakeContext:
    def __init__(self, text: str):
        self._text = text

    def new_page(self) -> _FakePage:
        return _FakePage(self._text)


def test_extract_items_from_order_applies_detail_date_to_summary_fallback() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    scraper.context = _FakeContext("Ihre Bestellung. Bestellung aufgegeben am 3. März 2025")
    scraper.save_debug_html = lambda *_args, **_kwargs: None

    order = OrderRecord(
        order_id="ORDER-1",
        order_date_text=None,
        order_date=None,
        order_total_text=None,
        status_text=None,
        detail_url="https://www.amazon.de/gp/your-account/order-details?orderID=ORDER-1",
        order_url=None,
        page_no=1,
        raw_text="Fallback summary title",
    )

    items = scraper.extract_items_from_order(order)

    assert len(items) == 1
    assert items[0].source == "summary_fallback"
    assert items[0].order_date == date(2025, 3, 3)


def test_scrape_items_for_orders_uses_order_history_links() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    order = OrderRecord(
        order_id="111-1234567-1234567",
        order_date_text="2. Dezember 2024",
        order_date=date(2024, 12, 2),
        order_total_text="13,90 €",
        status_text=None,
        detail_url="https://example.com/detail",
        order_url=None,
        page_no=1,
        raw_text="raw",
        item_links=[
            {"text": "UGREEN USB-C Cable", "href": "https://www.amazon.de/dp/B123"},
            {"text": "UGREEN USB-C Cable", "href": "https://www.amazon.de/dp/B123"},
        ],
    )

    items = scraper.scrape_items_for_orders([order])
    assert len(items) == 1
    assert items[0].source == "order_history"
    assert items[0].item_title == "UGREEN USB-C Cable"


def test_extract_items_from_order_history_falls_back_to_detail_page() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    order = OrderRecord(
        order_id="111-1234567-1234567",
        order_date_text="2. Dezember 2024",
        order_date=date(2024, 12, 2),
        order_total_text="13,90 €",
        status_text=None,
        detail_url="https://example.com/detail",
        order_url=None,
        page_no=1,
        raw_text="raw",
        item_links=[],
    )
    expected = [
        scraper.extract_items_from_summary_text(
            OrderRecord(
                order_id=order.order_id,
                order_date_text=order.order_date_text,
                order_date=order.order_date,
                order_total_text=order.order_total_text,
                status_text=order.status_text,
                detail_url=order.detail_url,
                order_url=order.order_url,
                page_no=order.page_no,
                raw_text="detail fallback",
            )
        )[0]
    ]
    scraper.extract_items_from_order = lambda _order: expected

    items = scraper.extract_items_from_order_history(order)

    assert items == expected
