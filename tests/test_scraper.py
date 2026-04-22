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
        self.url = "https://www.amazon.de/gp/css/order-history"

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def locator(self, _selector: str) -> _FakeLocator:
        return _FakeLocator(self._text)

    def evaluate(self, _script: str) -> list[dict[str, str]]:
        return []

    def close(self) -> None:
        return None

    def wait_for_load_state(self, _state: str) -> None:
        return None

    def wait_for_timeout(self, _timeout_ms: int) -> None:
        return None


class _GotoNextFakeLink:
    def __init__(self, page: "_GotoNextFakePage", href: str, visible: bool = True):
        self._page = page
        self._href = href
        self._visible = visible
        self.click_count = 0

    @property
    def first(self) -> "_GotoNextFakeLink":
        return self

    def count(self) -> int:
        return 1

    def is_visible(self) -> bool:
        return self._visible

    def get_attribute(self, name: str) -> str | None:
        if name == "href":
            return self._href
        return None

    def click(self) -> None:
        self.click_count += 1
        self._page.url = self._page.next_url_after_click


class _GotoNextFakeLocator:
    def __init__(self, link: _GotoNextFakeLink | None):
        self._link = link

    @property
    def first(self) -> _GotoNextFakeLink:
        assert self._link is not None
        return self._link

    def count(self) -> int:
        return 0 if self._link is None else 1


class _GotoNextFakePage:
    def __init__(self, href: str, next_url_after_click: str):
        self.url = "https://www.amazon.de/gp/css/order-history?startIndex=10"
        self.next_url_after_click = next_url_after_click
        self.clicked_selector: str | None = None
        self._link = _GotoNextFakeLink(self, href)
        self.goto_calls: list[str] = []

    def locator(self, selector: str) -> _GotoNextFakeLocator:
        if selector == "li.a-last a":
            self.clicked_selector = selector
            return _GotoNextFakeLocator(self._link)
        return _GotoNextFakeLocator(None)

    def wait_for_load_state(self, _state: str) -> None:
        return None

    def goto(self, url: str, **_kwargs) -> None:
        self.goto_calls.append(url)
        self.url = url

    def evaluate(self, _script: str) -> dict:
        return {"url": self.url, "title": "Orders", "pagination": []}


class _GotoNextEvalErrorFakePage(_GotoNextFakePage):
    def evaluate(self, _script: str) -> dict:
        raise RuntimeError("execution context was destroyed")


class _FakeContext:
    def __init__(self, text: str):
        self._text = text

    def new_page(self) -> _FakePage:
        return _FakePage(self._text)


class _LoginFakePage:
    def __init__(self):
        self.goto_calls: list[str] = []
        self.wait_timeout_calls: list[int] = []

    def goto(self, url: str, **_kwargs) -> None:
        self.goto_calls.append(url)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeout_calls.append(timeout_ms)


class _LoginFakeContext:
    def __init__(self):
        self.storage_state_calls: list[str] = []

    def storage_state(self, path: str) -> None:
        self.storage_state_calls.append(path)


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


def test_goto_next_page_ignores_non_order_history_candidate() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    scraper.page = _GotoNextFakePage(
        href="https://www.amazon.de/gp/product/B0TEST",
        next_url_after_click="https://www.amazon.de/gp/product/B0TEST",
    )

    moved = scraper.goto_next_page()

    assert moved is False
    assert scraper.page.url == "https://www.amazon.de/gp/css/order-history?startIndex=10"


def test_goto_next_page_recovers_when_navigation_leaves_order_history() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    scraper.page = _GotoNextFakePage(
        href="/gp/css/order-history?startIndex=20",
        next_url_after_click="https://www.amazon.de/gp/product/B0TEST",
    )

    moved = scraper.goto_next_page()

    assert moved is False
    assert scraper.page.goto_calls == ["https://www.amazon.de/gp/css/order-history?startIndex=10"]


def test_goto_next_page_stops_when_url_does_not_change() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    scraper.page = _GotoNextFakePage(
        href="/gp/css/order-history?startIndex=20",
        next_url_after_click="https://www.amazon.de/gp/css/order-history?startIndex=10",
    )

    moved = scraper.goto_next_page()

    assert moved is False


def test_goto_next_page_ignores_pagination_debug_errors() -> None:
    scraper = AmazonScraper(ScrapeConfig())
    scraper.page = _GotoNextEvalErrorFakePage(
        href="/gp/css/order-history?startIndex=20",
        next_url_after_click="https://www.amazon.de/gp/css/order-history?startIndex=20",
    )

    moved = scraper.goto_next_page()

    assert moved is True


def test_login_and_save_session_waits_when_stdin_is_not_interactive(monkeypatch, tmp_path) -> None:
    auth_file = tmp_path / "state.json"
    scraper = AmazonScraper(ScrapeConfig(auth_file=auth_file, login_wait_seconds=12))
    scraper.page = _LoginFakePage()
    scraper.context = _LoginFakeContext()

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    scraper.login_and_save_session()

    assert scraper.page.goto_calls == ["https://www.amazon.de/gp/css/order-history"]
    assert scraper.page.wait_timeout_calls == [12000]
    assert scraper.context.storage_state_calls == [str(auth_file)]


def test_login_and_save_session_does_not_save_when_interactive_input_eof(monkeypatch, tmp_path) -> None:
    auth_file = tmp_path / "state.json"
    scraper = AmazonScraper(ScrapeConfig(auth_file=auth_file, login_wait_seconds=12))
    scraper.page = _LoginFakePage()
    scraper.context = _LoginFakeContext()

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError))

    scraper.login_and_save_session()

    assert scraper.page.goto_calls == ["https://www.amazon.de/gp/css/order-history"]
    assert scraper.page.wait_timeout_calls == []
    assert scraper.context.storage_state_calls == []
