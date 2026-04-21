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
