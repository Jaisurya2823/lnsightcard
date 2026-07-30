"""
Plain text (.txt) exporter — for pasting into WhatsApp/email, or for
anyone who just wants the numbers without opening a PDF/Excel/Word
viewer. Same content as the console output, saved to a file.
"""

from __future__ import annotations

from pathlib import Path

from insightcard.config import BrandConfig
from insightcard.metrics import ReportMetrics


def build_txt(
    metrics: ReportMetrics,
    brand: BrandConfig,
    output_path: str | Path,
    data_quality=None,
) -> Path:
    lines: list[str] = []
    width = 60
    lines.append("=" * width)
    lines.append(f" {brand.report_title.upper()}")
    lines.append(f" {brand.business_name}")
    if metrics.date_range:
        lines.append(f" Period: {metrics.date_range[0]} to {metrics.date_range[1]}")
    lines.append("=" * width)
    lines.append("")

    lines.append(f"Total Revenue:        {brand.currency_symbol}{metrics.total_revenue:,.2f}")
    lines.append(f"Orders:               {metrics.order_count:,}")
    lines.append(f"Average Order Value:  {brand.currency_symbol}{metrics.average_order_value:,.2f}")
    if metrics.growth_pct is not None:
        lines.append(f"Growth (last period): {metrics.growth_pct:+.1f}%")
    lines.append("")

    if data_quality is not None:
        lines.append("-" * width)
        lines.append("DATA HEALTH CHECK")
        lines.append("-" * width)
        if data_quality.is_clean:
            lines.append(f"No data quality issues detected across {data_quality.total_rows:,} rows.")
        else:
            for warning in data_quality.warnings:
                lines.append(f"! {warning}")
        lines.append("")

    lines.append("-" * width)
    lines.append("KEY INSIGHTS")
    lines.append("-" * width)
    for insight in metrics.insights:
        lines.append(f"- {insight}")
    lines.append("")

    if metrics.top_products is not None and len(metrics.top_products):
        lines.append("-" * width)
        lines.append("TOP PRODUCTS")
        lines.append("-" * width)
        for rank, (name, revenue) in enumerate(metrics.top_products.items(), start=1):
            lines.append(f"  {rank}. {name:<30} {brand.currency_symbol}{revenue:,.2f}")
        lines.append("")

    if metrics.slow_moving_products is not None and len(metrics.slow_moving_products):
        lines.append("-" * width)
        lines.append("SLOW-MOVING STOCK (no sale in 30+ days)")
        lines.append("-" * width)
        for name, days in metrics.slow_moving_products.head(10).items():
            lines.append(f"  - {name:<30} last sold {int(days)} days ago")
        lines.append("")

    lines.append("=" * width)
    lines.append(f" {brand.footer_text}")
    lines.append("=" * width)

    output_path = Path(output_path)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
