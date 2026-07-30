"""
Chart generation. Every function here checks whether the data it
needs actually exists (e.g. a category column) and returns None
instead of raising — a real-world spreadsheet may not have every
column, and the report should still generate with whatever charts
are possible rather than fail entirely.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from insightcard.metrics import ReportMetrics, cap_with_other

_ACCENT_PALETTE = ["#1a237e", "#00897b", "#f9a825", "#c62828", "#6a1b9a", "#2e7d32"]


def plot_monthly_trend(m: ReportMetrics, out_dir: Path) -> Path | None:
    if m.monthly_revenue is None or len(m.monthly_revenue) < 2:
        return None
    fig, ax = plt.subplots(figsize=(8, 4.2))
    m.monthly_revenue.plot(kind="line", marker="o", ax=ax, color=_ACCENT_PALETTE[0])
    ax.set_title("Revenue Trend")
    ax.set_xlabel("")
    ax.set_ylabel("Revenue")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    path = out_dir / "chart_monthly_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_top_products(m: ReportMetrics, out_dir: Path) -> Path | None:
    if m.top_products is None or len(m.top_products) == 0:
        return None
    fig, ax = plt.subplots(figsize=(7, 4.2))
    m.top_products.sort_values().plot(kind="barh", ax=ax, color=_ACCENT_PALETTE[1])
    ax.set_title("Top Products by Revenue")
    ax.set_xlabel("Revenue")
    ax.set_ylabel("")
    fig.tight_layout()
    path = out_dir / "chart_top_products.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_category_split(m: ReportMetrics, out_dir: Path) -> Path | None:
    if m.top_categories is None or len(m.top_categories) < 2:
        return None
    capped = cap_with_other(m.top_categories, max_slices=8)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.pie(
        capped.values, labels=capped.index, autopct="%1.1f%%",
        startangle=90, colors=_ACCENT_PALETTE,
    )
    ax.set_title("Revenue Share by Category")
    ax.axis("equal")
    fig.tight_layout()
    path = out_dir / "chart_category_split.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_region_breakdown(m: ReportMetrics, out_dir: Path) -> Path | None:
    if m.top_regions is None or len(m.top_regions) < 2:
        return None
    capped = cap_with_other(m.top_regions, max_slices=12)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    capped.plot(kind="bar", ax=ax, color=_ACCENT_PALETTE[3])
    ax.set_title("Revenue by Region")
    ax.set_xlabel("")
    ax.set_ylabel("Revenue")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = out_dir / "chart_region_breakdown.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_weekday_revenue(m: ReportMetrics, out_dir: Path) -> Path | None:
    if m.weekday_revenue is None or len(m.weekday_revenue) < 2:
        return None
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [_ACCENT_PALETTE[4] if day in (m.best_worst_weekday or ()) else "#b0bec5" for day in m.weekday_revenue.index]
    m.weekday_revenue.plot(kind="bar", ax=ax, color=colors)
    ax.set_title("Revenue by Day of the Week")
    ax.set_xlabel("")
    ax.set_ylabel("Revenue")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = out_dir / "chart_weekday_revenue.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def generate_all_charts(m: ReportMetrics, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    charts = [
        plot_monthly_trend(m, out_dir),
        plot_top_products(m, out_dir),
        plot_category_split(m, out_dir),
        plot_region_breakdown(m, out_dir),
        plot_weekday_revenue(m, out_dir),
    ]
    return [c for c in charts if c is not None]
