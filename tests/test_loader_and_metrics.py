"""
Tests for column auto-detection and metrics computation.

test_detect_columns_on_pandas3_str_dtype is a regression test for a
real bug found during development: pandas 3.0 defaults text columns
to a native StringDtype ('str') instead of the legacy 'object' dtype,
which silently broke every `df[col].dtype == object` check in
loader.py (dates, products, categories, and regions all failed to
detect). We force that dtype explicitly here so the test fails again
if that check regresses.
"""

from __future__ import annotations

import pandas as pd
import pytest

from insightcard import loader, metrics as metrics_mod


def _messy_frame() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "Order Date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-02-01", "2024-02-02"],
            "Item": ["Cotton Kurti", "Denim Jacket", "Cotton Kurti", "Silver Anklet", "Denim Jacket"],
            "Segment": ["Apparel", "Apparel", "Apparel", "Jewellery", "Apparel"],
            "City": ["Mumbai", "Pune", "Mumbai", "Nagpur", "Pune"],
            "Units": [2, 1, 3, 1, 2],
            "Price (Rs)": [899.0, 2199.0, 899.0, 349.0, 2199.0],
        }
    )
    df["Total (Rs)"] = df["Units"] * df["Price (Rs)"]
    return df


def test_detect_columns_on_pandas3_str_dtype():
    df = _messy_frame()
    # Force pandas 3.0's native StringDtype explicitly, in case the
    # test environment's pandas version still defaults to 'object'.
    for col in ["Order Date", "Item", "Segment", "City"]:
        df[col] = df[col].astype("str")

    columns = loader.detect_columns(df)
    assert columns.date == "Order Date"
    assert columns.amount == "Total (Rs)"  # 'total' must outrank 'price'
    assert columns.quantity == "Units"
    assert columns.product == "Item"
    assert columns.category == "Segment"
    assert columns.region == "City"


def test_amount_detection_prefers_total_over_price():
    """A 'Total' column should always win over a unit 'Price' column,
    even when Price appears earlier in the sheet."""
    df = pd.DataFrame({"Price (Rs)": [10.0, 20.0], "Total (Rs)": [10.0, 40.0]})
    columns = loader.detect_columns(df)
    assert columns.amount == "Total (Rs)"


def test_category_and_region_not_swapped_on_abbreviated_headers():
    """Regression test: found via a realistic messy-spreadsheet stress
    test. 'Dept' (department/category values like 'Kitchenware',
    'Decor') and 'Town' (city values like 'Pune', 'Mumbai') previously
    got detected BACKWARDS -- 'Town' was labeled category and 'Dept'
    was labeled region -- because neither abbreviation matched the
    keyword lists ('department', 'city'), so detection fell back to
    picking whichever had higher cardinality among the leftover
    columns, in whichever order category-then-region happened to run.
    Fixed by adding 'dept' and 'town' (and similar synonyms) to the
    keyword lists so a keyword match wins before the cardinality
    fallback ever runs."""
    df = pd.DataFrame(
        {
            "Bill Date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "Item Name": ["Cup", "Cup", "Tray", "Tray"],
            "Dept": ["Kitchenware", "Kitchenware", "Decor", "Decor"],
            "Town": ["Pune", "Mumbai", "Pune", "Nagpur"],
            "Grand Total": [100.0, 150.0, 200.0, 250.0],
        }
    )
    columns = loader.detect_columns(df)
    assert columns.category == "Dept"
    assert columns.region == "Town"


def test_serial_number_column_never_mistaken_for_amount():
    """Regression test: found via a real user upload -- a course
    catalog file (S.No, Platform, Course, Direct Course Link) has NO
    revenue column at all, but 'S.No' (1, 2, 3...16) was the only
    numeric column, so the 'largest sum' fallback picked it and
    reported 'Total Revenue: Rs 136.00' -- literally 1+2+...+16, not
    money. Fixed two ways: (1) exact-match denylist of known ID column
    names ('s.no', 'id', 'index', etc.), and (2) a statistical check
    that catches a perfect 1-step sequence regardless of the column's
    name. Detection should now correctly return None for amount rather
    than silently fabricating a number."""
    df = pd.DataFrame(
        {
            "S.No": [1, 2, 3, 4, 5],
            "Platform": ["Oracle", "AWS", "Cisco", "AWS", "Salesforce"],
            "Course": ["Course A", "Course B", "Course C", "Course D", "Course E"],
            "Direct Course Link": [
                "https://a.example/1", "https://a.example/2", "https://a.example/3",
                "https://a.example/4", "https://a.example/5",
            ],
        }
    )
    columns = loader.detect_columns(df)
    assert columns.amount is None


def test_id_like_column_by_name_excluded_even_with_no_sequence():
    """A column named exactly 'ID' (not necessarily sequential) should
    still never be picked as amount -- checked by name, independent of
    the sequence-shape check."""
    df = pd.DataFrame({"ID": [5, 5, 5, 5], "Revenue": [100.0, 200.0, 150.0, 300.0]})
    columns = loader.detect_columns(df)
    assert columns.amount == "Revenue"


def test_normal_numeric_column_not_falsely_flagged_as_id():
    """A genuine revenue column (non-sequential, no ID-like name)
    must not be excluded by the new ID-column safeguard."""
    df = pd.DataFrame({"Sales": [532.0, 918.0, 204.0, 1500.0, 75.0]})
    columns = loader.detect_columns(df)
    assert columns.amount == "Sales"


def test_cap_with_other_limits_many_categories():
    """Regression test: found via a stress test with 40 categories --
    an uncapped pie chart with that many slices is unreadable (tiny
    slivers, and the accent color palette repeats after a handful of
    colors). cap_with_other() should reduce to max_slices entries,
    bucketing the remainder into 'Other', while the underlying
    ReportMetrics.top_categories used for insights/tables stays full."""
    series = pd.Series({f"Cat-{i}": float(100 - i) for i in range(40)}).sort_values(ascending=False)
    capped = metrics_mod.cap_with_other(series, max_slices=8)
    assert len(capped) == 8
    assert "Other" in capped.index
    assert capped["Other"] == series.iloc[7:].sum()


def test_cap_with_other_leaves_small_series_unchanged():
    series = pd.Series({"A": 100.0, "B": 50.0, "C": 25.0})
    capped = metrics_mod.cap_with_other(series, max_slices=8)
    pd.testing.assert_series_equal(capped, series)


def test_detect_columns_handles_missing_columns_gracefully():
    df = pd.DataFrame({"Revenue": [100.0, 200.0, 150.0]})
    columns = loader.detect_columns(df)
    assert columns.amount == "Revenue"
    assert columns.date is None
    assert columns.product is None


def test_normalize_renames_and_coerces_types():
    df = _messy_frame()
    columns = loader.detect_columns(df)
    normalized = loader.normalize(df, columns)
    assert "date" in normalized.columns
    assert "amount" in normalized.columns
    assert pd.api.types.is_datetime64_any_dtype(normalized["date"])
    assert pd.api.types.is_numeric_dtype(normalized["amount"])


def test_compute_metrics_basic_totals():
    df = _messy_frame()
    columns = loader.detect_columns(df)
    normalized = loader.normalize(df, columns)
    m = metrics_mod.compute_metrics(normalized)
    assert m.order_count == 5
    assert m.total_revenue == round(df["Total (Rs)"].sum(), 2)
    assert m.top_products is not None
    assert m.top_categories is not None


def test_compute_metrics_raises_without_amount_column():
    df = pd.DataFrame({"Notes": ["a", "b"]})
    with pytest.raises(ValueError):
        metrics_mod.compute_metrics(df)


def test_insights_are_generated_and_grounded():
    df = _messy_frame()
    columns = loader.detect_columns(df)
    normalized = loader.normalize(df, columns)
    m = metrics_mod.compute_metrics(normalized)
    assert len(m.insights) > 0
    # every product/category name mentioned should actually be in the data
    joined = " ".join(m.insights)
    if m.top_products is not None and len(m.top_products):
        assert m.top_products.index[0] in joined


def test_growth_pct_is_none_when_previous_period_is_negative():
    """Regression test: a previous period that's net negative (e.g. a
    month dominated by a refund) previously produced a nonsensical,
    exploding growth percentage like '2476.7%' by dividing by a small
    negative number. Growth should simply not be reported in that
    case rather than showing a misleading figure."""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-03-01", "2024-04-01"]),
        "amount": [-799.0, 18990.0],  # March net negative, April a big positive month
    })
    m = metrics_mod.compute_metrics(df)
    assert m.growth_pct is None
    assert not any("%" in i and ("dropped" in i or "grew" in i) for i in m.insights)


def test_product_share_of_revenue_never_exceeds_100_percent():
    """Regression test: when a refund is coded as its own negative-
    amount row (a separate 'product' rather than netted against the
    original sale), net total_revenue can be smaller than the sum of
    individual products' positive totals -- previously producing an
    impossible '103.3% of revenue' figure. Share percentages must now
    use gross positive revenue as the denominator and never exceed
    100%."""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
        "product": ["Saree", "Saree", "Kurti", "Return: Kurti"],
        "amount": [1899.0, 1899.0, 799.0, -799.0],
    })
    m = metrics_mod.compute_metrics(df)
    joined = " ".join(m.insights)
    import re
    for match in re.finditer(r"(\d+(?:\.\d+)?)%", joined):
        assert float(match.group(1)) <= 100.0, f"Found an impossible share > 100% in insights: {joined}"
