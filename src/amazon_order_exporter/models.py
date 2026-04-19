from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any


@dataclass(slots=True)
class OrderRecord:
    order_id: str
    order_date_text: str | None
    order_date: date | None
    order_total_text: str | None
    status_text: str | None
    detail_url: str | None
    order_url: str | None
    page_no: int
    raw_text: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["order_date"] = self.order_date.isoformat() if self.order_date else None
        return data


@dataclass(slots=True)
class ItemRecord:
    order_id: str
    order_date: date | None
    item_title: str
    product_url: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["order_date"] = self.order_date.isoformat() if self.order_date else None
        return data
