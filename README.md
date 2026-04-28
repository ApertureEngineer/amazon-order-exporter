# amazon-order-exporter

A small private Python repository to export product data from Amazon order history (personal account) into Excel.

## Goal

This repository fetches **order data, product titles, and available item price context**.

It does **not** perform business classification such as `personal` vs `commercial`. That classification can be done later manually or in a separate repository.

## Features

- Manual login with local session file
- Export for a fiscal year or a custom date range
- Product titles from order overview and order detail pages
- Item-level unit prices from order detail pages where Amazon exposes them
- Output to Excel (`orders`, `items`) and CSV
- Optional debug HTML for selector adjustments

## Setup

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -e .
playwright install chromium
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## 1) Save session

```bash
amazon-order-exporter login --domain amazon.de
```

Chromium will open. Log in manually once and then confirm in the terminal by pressing Enter.

If terminal input is not available (for example when launched from a GUI), the login flow now keeps the browser open for 180 seconds by default before saving. You can change this with:

```bash
amazon-order-exporter login --login-wait-seconds 300 --domain amazon.de
```

The session is stored locally at:

```text
.secrets/amazon_state.json
```

## 2) Export one year

```bash
amazon-order-exporter export --year 2025 --domain amazon.de --output data/output/amazon_orders_2025.xlsx
```

## 3) Export a date range

```bash
amazon-order-exporter export --date-from 2025-01-01 --date-to 2025-12-31 --domain amazon.de --output data/output/amazon_orders_2025.xlsx
```

## Output

The Excel file contains two sheets:

- `orders`: one row per order
- `items`: one row per product

Typical columns:

- `order_id`
- `order_date`
- `order_total_text`
- `status_text`
- `detail_url`
- `item_title`
- `item_title_short`
- `product_url`
- `item_price_text`
- `item_price_amount`
- `quantity_text`
- `price_source`

Additional CSV files are generated:

- `amazon_orders_2025.orders.csv`
- `amazon_orders_2025.items.csv`

## Notes

- Amazon occasionally changes HTML and button labels. If that happens, selectors in `scraper.py` must be adjusted.
- Amazon payments can be split across shipments, gift cards, refunds, or delayed charges. Item prices and order totals make bank reconciliation easier, but they may not always match a bank transaction one-to-one.
- This repository stores **no credentials**, only authenticated browser state.
- `.secrets/` should not be committed to a remote repository.

## Suggested next steps

- First real test with 2025 data
- Fine-tune selectors if needed
- Import into your personal finance workflow
