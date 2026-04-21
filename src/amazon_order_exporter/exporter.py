from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import ItemRecord, OrderRecord


class ExportPaths:
    def __init__(self, xlsx_path: Path):
        self.xlsx_path = xlsx_path
        self.orders_csv_path = xlsx_path.with_suffix(".orders.csv")
        self.items_csv_path = xlsx_path.with_suffix(".items.csv")


def write_outputs(orders: list[OrderRecord], items: list[ItemRecord], output_path: Path) -> ExportPaths:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paths = ExportPaths(output_path)

    orders_df = pd.DataFrame([row.to_dict() for row in orders])
    items_df = pd.DataFrame([row.to_dict() for row in items])

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

    if items_df.empty:
        items_df = pd.DataFrame(columns=[
            "order_id",
            "order_date",
            "item_title",
            "product_url",
            "source",
        ])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        orders_df.to_excel(writer, sheet_name="orders", index=False)
        items_df.to_excel(writer, sheet_name="items", index=False)

    orders_df.to_csv(paths.orders_csv_path, index=False, encoding="utf-8-sig")
    items_df.to_csv(paths.items_csv_path, index=False, encoding="utf-8-sig")

    return paths
