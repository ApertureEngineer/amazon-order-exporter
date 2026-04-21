from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .models import ItemRecord, OrderRecord
from .parsing import ORDER_ID_RE, in_range, parse_date, parse_order_date_text, parse_order_total_text, parse_status_text

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapeConfig:
    domain: str = "amazon.de"
    auth_file: Path = Path(".secrets/amazon_state.json")
    headless: bool = False
    slow_mo_ms: int = 50
    timeout_ms: int = 30000
    debug_dir: Path | None = None
    include_unknown_dates: bool = True

    @property
    def order_history_url(self) -> str:
        return f"https://www.{self.domain}/gp/css/order-history"


class AmazonScraper:
    def __init__(self, config: ScrapeConfig):
        self.config = config
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self) -> "AmazonScraper":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
        )
        if self.config.auth_file.exists():
            self.context = self.browser.new_context(
                storage_state=str(self.config.auth_file),
                locale="de-DE",
            )
        else:
            self.context = self.browser.new_context(locale="de-DE")
        self.context.set_default_timeout(self.config.timeout_ms)
        self.page = self.context.new_page()

    def close(self) -> None:
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self._playwright:
            self._playwright.stop()

    @property
    def current_page(self) -> Page:
        if not self.page:
            raise RuntimeError("Scraper not started")
        return self.page

    def ensure_debug_dir(self) -> Path | None:
        if not self.config.debug_dir:
            return None
        self.config.debug_dir.mkdir(parents=True, exist_ok=True)
        return self.config.debug_dir

    def save_debug_html(self, name: str, page: Page | None = None) -> None:
        debug_dir = self.ensure_debug_dir()
        if not debug_dir:
            return
        current_page = page or self.current_page
        path = debug_dir / f"{name}.html"
        path.write_text(current_page.content(), encoding="utf-8")

    def login_and_save_session(self) -> None:
        page = self.current_page
        page.goto(self.config.order_history_url, wait_until="domcontentloaded")
        LOGGER.info("Please log in to Amazon manually, then press Enter in the terminal.")
        input("Press Enter after login (and 2FA, if required) is complete... ")
        self.config.auth_file.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(self.config.auth_file))
        LOGGER.info("Session saved to %s", self.config.auth_file)

    def open_order_history(self) -> None:
        page = self.current_page
        page.goto(self.config.order_history_url, wait_until="domcontentloaded")
        time.sleep(2)
        self.save_debug_html("order_history_initial")

    def try_select_year_filter(self, year: int) -> bool:
        page = self.current_page
        year_text = str(year)
        selectors = [
            "select[name*='timeFilter']",
            "select#time-filter",
            "select[name='orderFilter']",
            "select",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if locator.count() == 0:
                    continue
                for idx in range(locator.count()):
                    select = locator.nth(idx)
                    options = select.locator("option")
                    texts = [options.nth(i).inner_text().strip() for i in range(options.count())]
                    if any(year_text in text for text in texts):
                        option_value = None
                        for i in range(options.count()):
                            text = options.nth(i).inner_text().strip()
                            if year_text in text:
                                option_value = options.nth(i).get_attribute("value") or text
                                break
                        if option_value:
                            LOGGER.info("Trying to set year filter %s via %s", year, selector)
                            select.select_option(value=option_value)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                            self.save_debug_html(f"year_filter_{year}")
                            return True
            except Exception:
                continue
        LOGGER.warning(
            "Year filter %s could not be set automatically. Export will filter locally by order date.",
            year,
        )
        return False

    def extract_order_blocks(self, page_no: int) -> list[OrderRecord]:
        page = self.current_page
        blocks = page.evaluate(
            r"""
            () => {
              const orderRegex = /\b\d{3}-\d{7}-\d{7}\b/g;
              const nodes = Array.from(document.querySelectorAll('div, section, article, li'));
              const results = [];

              for (const el of nodes) {
                const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
                if (!text) continue;
                const ids = text.match(orderRegex);
                if (!ids) continue;
                if (text.length < 60 || text.length > 9000) continue;

                const links = Array.from(el.querySelectorAll('a[href]')).map(a => ({
                  text: (a.innerText || '').replace(/\s+/g, ' ').trim(),
                  href: a.href
                }));
                const productLinks = links.filter(link => {
                  const href = link.href || '';
                  const title = link.text || '';
                  if (!(href.includes('/dp/') || href.includes('/gp/product/'))) return false;
                  if (title.length < 6) return false;

                  const lower = title.toLowerCase();
                  const blacklist = [
                    "amazon visa",
                    "amazon business amex card",
                    "nochmals kaufen",
                    "deinen artikel anzeigen",
                    "produktsupport erhalten",
                    "schreib eine produktrezension",
                    "dein spar-abo anzeigen",
                    "status der rücksendung",
                    "problem bei bestellung",
                    "rücksendeetikett und anleitung",
                    "frage zum produkt",
                    "zu deiner software-bibliothek",
                    "bestelldetails anzeigen",
                    "rechnung"
                  ];
                  return !blacklist.some(entry => lower.includes(entry));
                });

                results.push({
                  text,
                  order_ids: Array.from(new Set(ids)),
                  links,
                  item_links: productLinks,
                });
              }
              return results;
            }
            """
        )

        best_by_order_id: dict[str, dict] = {}
        for block in blocks:
            block_text = block["text"]
            score = abs(len(block_text) - 1000)
            for order_id in block["order_ids"]:
                existing = best_by_order_id.get(order_id)
                if existing is None or score < existing["_score"]:
                    detail_url = None
                    order_url = None
                    for link in block["links"]:
                        href = link.get("href") or ""
                        text = (link.get("text") or "").lower()
                        if order_id in href and ("detail" in href or "details" in href or "bestellung" in text or "order" in text):
                            detail_url = href
                            break
                    for link in block["links"]:
                        href = link.get("href") or ""
                        if order_id in href:
                            order_url = href
                            if detail_url is None:
                                detail_url = href
                    scoped_item_links = block["item_links"] if len(block["order_ids"]) == 1 else []
                    best_by_order_id[order_id] = {
                        "_score": score,
                        "text": block_text,
                        "detail_url": detail_url,
                        "order_url": order_url,
                        "item_links": scoped_item_links,
                    }

        records: list[OrderRecord] = []
        for order_id, payload in best_by_order_id.items():
            raw_text = payload["text"]
            order_date_text = parse_order_date_text(raw_text)
            order_date = parse_date(order_date_text)
            records.append(
                OrderRecord(
                    order_id=order_id,
                    order_date_text=order_date_text,
                    order_date=order_date,
                    order_total_text=parse_order_total_text(raw_text),
                    status_text=parse_status_text(raw_text),
                    detail_url=payload["detail_url"],
                    order_url=payload["order_url"],
                    page_no=page_no,
                    raw_text=raw_text,
                    item_links=payload["item_links"],
                )
            )

        records.sort(key=lambda record: record.order_id)
        return records

    def goto_next_page(self) -> bool:
        page = self.current_page
        current_url = page.url
        selectors = [
            "li.a-last a",
            ".a-pagination a[aria-label*='Nächste']",
            ".a-pagination a[aria-label*='Weiter']",
            ".a-pagination a[aria-label*='Next']",
            "a:has-text('Nächste')",
            "a:has-text('Weiter')",
            "a:has-text('Next')",
        ]
        for selector in selectors:
            locator = page.locator(selector)
            try:
                if locator.count() > 0 and locator.first.is_visible():
                    LOGGER.info("Found next-page selector: %s", selector)
                    candidate_href = locator.first.get_attribute("href") or ""
                    if candidate_href and "order-history" not in candidate_href and "startIndex=" not in candidate_href:
                        LOGGER.warning(
                            "Ignoring next-page candidate because it does not look like order-history pagination: %s",
                            candidate_href,
                        )
                        continue
                    locator.first.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)
                    if "order-history" not in page.url:
                        LOGGER.warning(
                            "Pagination click navigated away from order-history (%s). Returning to %s and stopping pagination.",
                            page.url,
                            current_url,
                        )
                        page.goto(current_url, wait_until="domcontentloaded")
                        time.sleep(1)
                        return False
                    return True
            except Exception:
                continue
        LOGGER.info("No next-page selector found.")
        return False

    def scrape_orders(
        self,
        date_from: date | None,
        date_to: date | None,
        max_pages: int = 25,
        target_year: int | None = None,
    ) -> list[OrderRecord]:
        self.open_order_history()
        if target_year:
            self.try_select_year_filter(target_year)

        all_records: list[OrderRecord] = []
        seen_order_ids: set[str] = set()

        for page_no in range(1, max_pages + 1):
            LOGGER.info("Reading order overview page %s", page_no)
            records = self.extract_order_blocks(page_no=page_no)
            LOGGER.info("[page %s] url=%s orders=%s", page_no, self.current_page.url, len(records))
            if not records:
                LOGGER.warning("No order blocks found on page %s", page_no)
                self.save_debug_html(f"orders_page_{page_no}")
                break

            for record in records:
                if record.order_id in seen_order_ids:
                    continue
                seen_order_ids.add(record.order_id)
                if in_range(
                    record.order_date,
                    date_from,
                    date_to,
                    include_unknown_when_filtered=self.config.include_unknown_dates,
                ):
                    all_records.append(record)

            oldest_visible = min((record.order_date for record in records if record.order_date), default=None)
            if oldest_visible and date_from and oldest_visible < date_from:
                LOGGER.info("Oldest visible date on page %s is before date-from. Stopping pagination.", page_no)
                break

            if page_no >= max_pages:
                LOGGER.info("Reached maximum number of pages: %s", max_pages)
                break

            if not self.goto_next_page():
                break

        return all_records

    def _normalize_detail_url(self, url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urljoin(f"https://www.{self.config.domain}", url)

    def extract_items_from_order(self, order: OrderRecord) -> list[ItemRecord]:
        if not order.detail_url:
            return []

        detail_url = self._normalize_detail_url(order.detail_url)
        if not detail_url:
            return []

        page = self.context.new_page()
        try:
            page.goto(detail_url, wait_until="domcontentloaded")
            time.sleep(2)
            self.save_debug_html(f"detail_{order.order_id}", page=page)
            page_text = page.locator("body").inner_text()
            fallback_date = order.order_date
            if fallback_date is None:
                fallback_date_text = parse_order_date_text(page_text)
                fallback_date = parse_date(fallback_date_text)
            products = page.evaluate(
                r"""
                () => {
                  const anchors = Array.from(document.querySelectorAll("main a[href], #a-page a[href], body a[href]"));
                  const result = [];

                  const isBadText = (text) => {
                    if (!text) return true;
                    if (text.length < 5 || text.length > 400) return true;
                    if (/^ASIN/i.test(text)) return true;
                    if (/^[0-9]+([.,][0-9]+)?\s*€(\s*[0-9]+([.,][0-9]+)?\s*€)?$/.test(text)) return true;

                    const normalized = text.toLowerCase();
                    const ctaLabels = [
                      "view your item",
                      "track package",
                      "buy it again",
                      "write a product review",
                      "leave seller feedback",
                      "return or replace items",
                      "get product support",
                      "problem with order",
                      "view order details",
                      "invoice"
                    ];
                    if (ctaLabels.includes(normalized)) return true;

                    return false;
                  };

                  const isBadHref = (href) => {
                    if (!href) return true;

                    const badPatterns = [
                      "ci_mcx",
                      "mr__d_sccl",
                      "pd_rd_",
                      "sp_csd",
                      "cm_cr_arp",
                      "/gp/buyagain",
                      "/s?",
                      "node="
                    ];

                    return badPatterns.some(p => href.includes(p));
                  };

                  for (const a of anchors) {
                    const href = a.href || '';
                    const text = (a.innerText || '').replace(/\s+/g, ' ').trim();

                    if (!(href.includes('/dp/') || href.includes('/gp/product/'))) {
                      continue;
                    }
                    if (isBadText(text)) continue;
                    if (isBadHref(href)) continue;

                    result.push({title: text, href});
                  }
                  return result;
                }
                """
            )
            deduped: list[ItemRecord] = []
            seen: set[tuple[str, str | None]] = set()
            for product in products:
                title = " ".join((product.get("title") or "").split())
                href = product.get("href")
                key = (title, href)
                if len(title) < 5 or key in seen:
                    continue
                seen.add(key)
                deduped.append(
                    ItemRecord(
                        order_id=order.order_id,
                        order_date=fallback_date,
                        item_title=title,
                        product_url=href,
                        source="detail_page",
                    )
                )

            if deduped:
                return deduped

            fallback_order = order if fallback_date == order.order_date else replace(order, order_date=fallback_date)
            return self.extract_items_from_summary_text(fallback_order)
        finally:
            page.close()

    def extract_items_from_summary_text(self, order: OrderRecord) -> list[ItemRecord]:
        summary = " ".join(order.raw_text.split())
        if not summary or ORDER_ID_RE.search(summary):
            summary = order.raw_text[:300]
        if not summary:
            return []
        return [
            ItemRecord(
                order_id=order.order_id,
                order_date=order.order_date,
                item_title=summary[:300],
                product_url=None,
                source="summary_fallback",
            )
        ]

    def extract_items_from_order_history(self, order: OrderRecord) -> list[ItemRecord]:
        item_links = order.item_links or []
        results: list[ItemRecord] = []
        seen: set[tuple[str, str | None]] = set()
        for item in item_links:
            title = " ".join((item.get("text") or "").split())
            href = item.get("href")
            key = (title, href)
            if len(title) < 5 or key in seen:
                continue
            seen.add(key)
            results.append(
                ItemRecord(
                    order_id=order.order_id,
                    order_date=order.order_date,
                    item_title=title,
                    product_url=href,
                    source="order_history",
                )
            )

        if results:
            return results
        if order.detail_url:
            return self.extract_items_from_order(order)
        return self.extract_items_from_summary_text(order)

    def scrape_items_for_orders(self, orders: Iterable[OrderRecord]) -> list[ItemRecord]:
        order_list = list(orders)
        items: list[ItemRecord] = []
        for idx, order in enumerate(order_list, start=1):
            LOGGER.info("Reading order items %s/%s: %s", idx, len(order_list), order.order_id)
            try:
                order_items = self.extract_items_from_order_history(order)
                items.extend(order_items)
                LOGGER.info("  Found %s items", len(order_items))
            except Exception as exc:
                LOGGER.exception("Error while reading order items for %s: %s", order.order_id, exc)
        return items
