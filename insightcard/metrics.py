"""
Computes the numeric metrics and turns a few of them into plain-
English sentences — WITHOUT calling any LLM API. This is deliberate:
the product is a one-time purchase, run entirely offline/locally, so
there's no per-report API cost eating into a one-time sale. Every
sentence below is a template filled from a number already computed,
never an invented claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ReportMetrics:
    total_revenue: float
    order_count: int
    average_order_value: float
    date_range: tuple[str, str] | None
    growth_pct: float | None  # vs previous equal-length period, None if not enough history
    top_products: pd.Series | None
    top_categories: pd.Series | None
    top_regions: pd.Series | None
    monthly_revenue: pd.Series | None
    best_period: tuple[str, float] | None
    worst_period: tuple[str, float] | None
    weekday_revenue: pd.Series | None
    best_worst_weekday: tuple[str, str] | None  # (best day name, worst day name)
    slow_moving_products: pd.Series | None  # product -> days since last sale
    gross_positive_revenue: float  # sum of positive-amount rows only; see note in _build_insights
    insights: list[str] = field(default_factory=list)


def cap_with_other(series: pd.Series, max_slices: int = 8) -> pd.Series:
    """Caps a sorted-descending revenue breakdown to the top
    (max_slices - 1) entries plus a summed 'Other' bucket for the
    rest -- used before rendering a pie/bar chart. Found necessary via
    a stress test with 40 categories: an uncapped pie chart with that
    many slices is unreadable (tiny slivers, and the accent palette
    only has a handful of distinct colors so slices start repeating
    colors and become indistinguishable). Returns the series unchanged
    if it already fits within max_slices. Full, uncapped data is still
    used for every numeric calculation (totals, insights) -- this only
    affects what a chart/table displays."""
    if len(series) <= max_slices:
        return series
    top = series.iloc[: max_slices - 1]
    other_sum = series.iloc[max_slices - 1 :].sum()
    capped = pd.concat([top, pd.Series({"Other": other_sum})])
    return capped


def _period_growth(df: pd.DataFrame) -> tuple[float | None, pd.Series | None]:
    if "date" not in df.columns or df["date"].isna().all():
        return None, None
    monthly = df.dropna(subset=["date"]).groupby(df["date"].dt.to_period("M"))["amount"].sum()
    if len(monthly) < 2:
        return None, monthly if len(monthly) else None
    latest, previous = monthly.iloc[-1], monthly.iloc[-2]
    if previous <= 0:
        # A zero or negative baseline period (e.g. a month that was net
        # negative due to refunds) makes a percentage-growth figure
        # meaningless or wildly distorted (division by a tiny/negative
        # number can produce a nonsensical four-digit percentage) --
        # better to skip the figure than report something misleading.
        return None, monthly
    growth = round(((latest - previous) / previous) * 100, 1)
    return growth, monthly


_WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weekday_revenue(df: pd.DataFrame) -> tuple[pd.Series | None, tuple[str, str] | None]:
    if "date" not in df.columns:
        return None, None
    clean = df.dropna(subset=["date", "amount"])
    if clean.empty:
        return None, None
    grouped = clean.groupby(clean["date"].dt.day_name())["amount"].sum()
    grouped = grouped.reindex(_WEEKDAY_ORDER).dropna()
    if len(grouped) < 2:
        return (grouped if len(grouped) else None), None
    best_day = str(grouped.idxmax())
    worst_day = str(grouped.idxmin())
    return grouped.round(2), (best_day, worst_day)


def _slow_moving_products(df: pd.DataFrame, cutoff_days: int = 30) -> pd.Series | None:
    """Days since each product's last sale, relative to the most recent
    date IN THE DATA (not today's real-world date — this analyzes a
    historical export, not a live feed). Only flags products whose
    last sale is more than `cutoff_days` before that reference date,
    so a product simply not yet due for its next sale isn't flagged."""
    if "date" not in df.columns or "product" not in df.columns:
        return None
    clean = df.dropna(subset=["date", "product"])
    if clean.empty:
        return None
    reference_date = clean["date"].max()
    last_sale = clean.groupby("product")["date"].max()
    days_since = (reference_date - last_sale).dt.days
    slow = days_since[days_since > cutoff_days].sort_values(ascending=False)
    return slow if len(slow) else None


def compute_metrics(df: pd.DataFrame, top_n: int = 5) -> ReportMetrics:
    if "amount" not in df.columns:
        raise ValueError(
            "No amount/revenue column detected or provided. Pass --amount-col to specify it."
        )

    clean = df.dropna(subset=["amount"])
    total_revenue = round(float(clean["amount"].sum()), 2)
    order_count = len(clean)
    aov = round(total_revenue / order_count, 2) if order_count else 0.0
    # Used as the denominator for "share of revenue" percentages
    # instead of total_revenue -- see _build_insights for why.
    gross_positive_revenue = round(float(clean.loc[clean["amount"] > 0, "amount"].sum()), 2)

    date_range = None
    if "date" in clean.columns and clean["date"].notna().any():
        date_range = (
            clean["date"].min().date().isoformat(),
            clean["date"].max().date().isoformat(),
        )

    growth_pct, monthly = _period_growth(clean)

    top_products = None
    if "product" in clean.columns:
        top_products = clean.groupby("product")["amount"].sum().sort_values(ascending=False).head(top_n).round(2)

    top_categories = None
    if "category" in clean.columns:
        top_categories = clean.groupby("category")["amount"].sum().sort_values(ascending=False).round(2)

    top_regions = None
    if "region" in clean.columns:
        top_regions = clean.groupby("region")["amount"].sum().sort_values(ascending=False).round(2)

    best_period = worst_period = None
    if monthly is not None and len(monthly):
        best_period = (str(monthly.idxmax()), round(float(monthly.max()), 2))
        worst_period = (str(monthly.idxmin()), round(float(monthly.min()), 2))

    weekday_revenue, best_worst_weekday = _weekday_revenue(clean)
    slow_moving = _slow_moving_products(clean)

    metrics = ReportMetrics(
        total_revenue=total_revenue,
        order_count=order_count,
        average_order_value=aov,
        date_range=date_range,
        growth_pct=growth_pct,
        top_products=top_products,
        top_categories=top_categories,
        top_regions=top_regions,
        monthly_revenue=monthly,
        best_period=best_period,
        worst_period=worst_period,
        weekday_revenue=weekday_revenue,
        best_worst_weekday=best_worst_weekday,
        slow_moving_products=slow_moving,
        gross_positive_revenue=gross_positive_revenue,
    )
    metrics.insights = _build_insights(metrics)
    return metrics


def _build_insights(m: ReportMetrics) -> list[str]:
    """Template sentences, each gated on the specific number that
    justifies it existing — nothing here is inferred beyond the data."""
    insights: list[str] = []

    if m.growth_pct is not None:
        if m.growth_pct > 0:
            insights.append(f"Revenue grew {m.growth_pct}% in the most recent period compared to the one before it.")
        elif m.growth_pct < 0:
            insights.append(
                f"Revenue dropped {abs(m.growth_pct)}% in the most recent period compared to the one before it — "
                "worth a closer look at what changed."
            )
        else:
            insights.append("Revenue was flat between the two most recent periods.")

    if m.top_products is not None and len(m.top_products):
        top_name = m.top_products.index[0]
        # Use gross POSITIVE revenue as the denominator, not net total_revenue.
        # If refunds/returns are coded as separate negative-amount rows (a
        # common real-world pattern -- e.g. "Return: Product X" as its own
        # line rather than netted against the original sale), net revenue
        # can be smaller than the sum of individual products' positive
        # totals, which would otherwise make a "top 3 products" share
        # exceed 100% -- a nonsensical, misleading figure.
        denominator = m.gross_positive_revenue
        top_share = round((m.top_products.iloc[0] / denominator) * 100, 1) if denominator else 0
        if top_share <= 100:
            insights.append(f"'{top_name}' is the single largest contributor, at {top_share}% of total revenue.")
        if len(m.top_products) >= 3:
            top3_share = round((m.top_products.head(3).sum() / denominator) * 100, 1) if denominator else 0
            if 60 < top3_share <= 100:
                insights.append(
                    f"The top 3 products account for {top3_share}% of revenue — concentration risk if any one of "
                    "them slows down."
                )

    if m.top_categories is not None and len(m.top_categories) > 1:
        leader = m.top_categories.index[0]
        denominator = m.gross_positive_revenue
        leader_share = round((m.top_categories.iloc[0] / denominator) * 100, 1) if denominator else 0
        if leader_share <= 100:
            insights.append(f"'{leader}' is the strongest category, contributing {leader_share}% of revenue.")

    if m.top_regions is not None and len(m.top_regions) > 1:
        weakest = m.top_regions.index[-1]
        insights.append(f"'{weakest}' is the lowest-revenue region in this data — a possible growth opportunity.")

    if m.best_period and m.worst_period and m.best_period != m.worst_period:
        insights.append(
            f"{m.best_period[0]} was the strongest period (Rs {m.best_period[1]:,.2f}); "
            f"{m.worst_period[0]} was the weakest (Rs {m.worst_period[1]:,.2f})."
        )

    if m.best_worst_weekday:
        best_day, worst_day = m.best_worst_weekday
        insights.append(f"{best_day} is typically the busiest day for revenue; {worst_day} is typically the slowest.")

    if m.slow_moving_products is not None and len(m.slow_moving_products):
        count = len(m.slow_moving_products)
        top_name = m.slow_moving_products.index[0]
        top_days = int(m.slow_moving_products.iloc[0])
        if count == 1:
            insights.append(f"'{top_name}' hasn't sold in {top_days} days — consider a discount or bundle to clear it.")
        else:
            insights.append(
                f"{count} product(s) haven't sold in over 30 days, the longest being '{top_name}' "
                f"({top_days} days) — worth reviewing for a clearance push or discontinuing."
            )

    if not insights:
        insights.append("Not enough structured detail (dates/products/categories) was found to generate deeper insights — the summary metrics above still apply.")

    return insights
