"""
Data health checks over the normalized DataFrame — catches the
mistakes that happen constantly in a hand-maintained sales sheet:
accidental duplicate rows, blank cells, refunds miscoded as negative
sales, zero-amount placeholder rows, and typos that turn Rs 500 into
Rs 5,000. None of this requires an LLM — it's straightforward
statistics (IQR outlier detection, duplicate/na counts).

Every check is independent and gated on the columns actually being
present, same pattern as metrics.py and charts.py — a sheet without a
date column still gets amount-based checks, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class DataQualityReport:
    total_rows: int
    duplicate_rows: int = 0
    missing_amount_rows: int = 0
    missing_date_rows: int = 0
    negative_amount_rows: int = 0
    zero_amount_rows: int = 0
    outlier_rows: int = 0
    outlier_examples: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.warnings


def _detect_outliers(amounts: pd.Series) -> tuple[int, list[float]]:
    """IQR method: flags values far above the normal spread — the
    classic signature of a typo (an extra zero, a misplaced decimal)
    rather than a genuinely large legitimate order."""
    clean = amounts.dropna()
    clean = clean[clean > 0]
    if len(clean) < 5:
        return 0, []
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0, []
    upper_bound = q3 + 3 * iqr  # 3x (not the usual 1.5x) to only flag extreme cases
    outliers = clean[clean > upper_bound]
    return len(outliers), sorted(outliers.tolist(), reverse=True)[:5]


def check_data_quality(df: pd.DataFrame) -> DataQualityReport:
    total_rows = len(df)
    report = DataQualityReport(total_rows=total_rows)

    dup_subset = [c for c in ("date", "product", "amount", "quantity") if c in df.columns]
    if dup_subset:
        report.duplicate_rows = int(df.duplicated(subset=dup_subset, keep="first").sum())

    if "amount" in df.columns:
        report.missing_amount_rows = int(df["amount"].isna().sum())
        valid_amounts = df["amount"].dropna()
        report.negative_amount_rows = int((valid_amounts < 0).sum())
        report.zero_amount_rows = int((valid_amounts == 0).sum())
        report.outlier_rows, report.outlier_examples = _detect_outliers(valid_amounts)

    if "date" in df.columns:
        report.missing_date_rows = int(df["date"].isna().sum())

    report.warnings = _build_warnings(report)
    return report


def _build_warnings(r: DataQualityReport) -> list[str]:
    warnings: list[str] = []

    if r.duplicate_rows > 0:
        warnings.append(
            f"{r.duplicate_rows} row(s) look like duplicate entries (same date, product, and amount) — "
            "check for accidental double-entry."
        )
    if r.missing_amount_rows > 0:
        warnings.append(
            f"{r.missing_amount_rows} row(s) have a blank amount and were excluded from the totals above."
        )
    if r.missing_date_rows > 0:
        warnings.append(
            f"{r.missing_date_rows} row(s) have a blank or unreadable date, so they're left out of "
            "any trend/monthly charts."
        )
    if r.negative_amount_rows > 0:
        warnings.append(
            f"{r.negative_amount_rows} row(s) have negative revenue — confirm these are refunds/returns "
            "and not a data-entry mistake."
        )
    if r.zero_amount_rows > 0:
        warnings.append(
            f"{r.zero_amount_rows} row(s) have exactly zero revenue — worth confirming these are "
            "intentional (e.g. free samples) rather than a missed price entry."
        )
    if r.outlier_rows > 0:
        examples = ", ".join(f"{v:,.2f}" for v in r.outlier_examples)
        warnings.append(
            f"{r.outlier_rows} order(s) are unusually large compared to the rest of your data "
            f"(e.g. {examples}) — worth double-checking for typos like an extra zero."
        )

    return warnings
