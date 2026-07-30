"""
Branding + column-mapping config for a report run.

Kept as one small dataclass module so a future web UI or a different
CLI can build a BrandConfig/ColumnMap the same way the CLI does,
without duplicating logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BrandConfig:
    """What makes a report *look like yours* — no code changes needed
    per customer, just different values here."""

    business_name: str = "Your Business"
    report_title: str = "Business Insights Report"
    accent_color: tuple[int, int, int] = (26, 35, 126)  # navy, matches (0x1a, 0x23, 0x7e)
    footer_text: str = "Generated with InsightCard"
    currency_symbol: str = "Rs "


@dataclass
class ColumnMap:
    """Which real column in the user's file plays which logical role.
    Any field can be None — every downstream metric/chart function
    checks for that and skips gracefully rather than crashing, since
    we can't assume every spreadsheet has every column."""

    date: str | None = None
    amount: str | None = None
    quantity: str | None = None
    product: str | None = None
    category: str | None = None
    region: str | None = None

    def as_dict(self) -> dict:
        return {
            "date": self.date, "amount": self.amount, "quantity": self.quantity,
            "product": self.product, "category": self.category, "region": self.region,
        }
