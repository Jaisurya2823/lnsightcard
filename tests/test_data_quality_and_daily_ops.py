"""Tests for the data-quality checks and the new daily-ops metrics
(weekday revenue, slow-moving product detection)."""

from __future__ import annotations

import pandas as pd
import pytest

from insightcard import data_quality, metrics as metrics_mod


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22", "2024-01-29"]
            ),
            "product": ["Mug", "Mug", "Mug", "Mug", "Mug"],
            "amount": [100.0, 100.0, 100.0, 100.0, 100.0],
            "quantity": [1, 1, 1, 1, 1],
        }
    )


# --------------------------------------------------------------- data_quality

def test_clean_data_has_no_warnings():
    df = _base_frame()
    report = data_quality.check_data_quality(df)
    assert report.is_clean
    assert report.warnings == []


def test_detects_duplicate_rows():
    df = _base_frame()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplicate the first row
    report = data_quality.check_data_quality(df)
    assert report.duplicate_rows == 1
    assert any("duplicate" in w.lower() for w in report.warnings)


def test_detects_missing_amount():
    df = _base_frame()
    df.loc[0, "amount"] = None
    report = data_quality.check_data_quality(df)
    assert report.missing_amount_rows == 1
    assert any("blank amount" in w for w in report.warnings)


def test_detects_negative_and_zero_amounts():
    df = _base_frame()
    df.loc[0, "amount"] = -50.0
    df.loc[1, "amount"] = 0.0
    report = data_quality.check_data_quality(df)
    assert report.negative_amount_rows == 1
    assert report.zero_amount_rows == 1


def test_detects_outlier_amount():
    df = pd.DataFrame({"amount": [100.0, 105.0, 98.0, 102.0, 101.0, 99.0, 25000.0]})
    report = data_quality.check_data_quality(df)
    assert report.outlier_rows == 1
    assert 25000.0 in report.outlier_examples


def test_missing_columns_dont_crash():
    df = pd.DataFrame({"notes": ["a", "b"]})
    report = data_quality.check_data_quality(df)
    assert report.is_clean  # nothing to check, so nothing to warn about


# --------------------------------------------------------------- weekday revenue

def test_weekday_revenue_identifies_best_and_worst():
    df = pd.DataFrame(
        {
            # 2024-01-01 is a Monday
            "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-03", "2024-01-10"]),
            "amount": [500.0, 500.0, 50.0, 50.0],
        }
    )
    weekday_rev, best_worst = metrics_mod._weekday_revenue(df)
    assert weekday_rev is not None
    assert best_worst is not None
    best_day, worst_day = best_worst
    assert best_day == "Monday"
    assert worst_day == "Wednesday"


# --------------------------------------------------------------- slow-moving

def test_slow_moving_flags_old_product():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-06-01", "2024-06-05", "2024-06-10"]),
            "product": ["OldStock", "FreshItem", "FreshItem", "FreshItem"],
            "amount": [100.0, 100.0, 100.0, 100.0],
        }
    )
    slow = metrics_mod._slow_moving_products(df, cutoff_days=30)
    assert slow is not None
    assert "OldStock" in slow.index
    assert "FreshItem" not in slow.index


def test_slow_moving_none_when_all_recent():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-01", "2024-06-05", "2024-06-10"]),
            "product": ["A", "B", "C"],
            "amount": [100.0, 100.0, 100.0],
        }
    )
    slow = metrics_mod._slow_moving_products(df, cutoff_days=30)
    assert slow is None


def test_compute_metrics_includes_new_fields():
    df = _base_frame()
    m = metrics_mod.compute_metrics(df)
    assert m.weekday_revenue is not None
    # single-product frame with regular weekly sales shouldn't trigger slow-moving
    # (last sale is the most recent date in the data itself)
    assert m.slow_moving_products is None
