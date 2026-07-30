"""
Column-detection accuracy benchmark across realistic business
spreadsheet schemas — measured, not asserted. Each case is a schema a
real business might actually have, with the ground-truth answer for
what each logical role should map to. Run as a normal pytest test so
CI catches any regression in detection accuracy, and prints the
measured percentage so it's visible in test output, not just a
pass/fail.

This grew out of two real bugs found via this exact kind of testing:
  1. 'Dept'/'Town' (category/region) got detected backwards because
     neither abbreviation matched the keyword lists.
  2. 'SKU'/'Product Category' (product/category) got swapped because
     the generic word 'product' matched inside 'Product Category'
     before the more specific 'sku' keyword was checked.
Both are now individually regression-tested elsewhere; this file
covers the broader picture across many schemas at once.
"""

from __future__ import annotations

import pandas as pd
import pytest

from insightcard import loader

# Each case: (name, dataframe, expected mapping for the roles that
# MUST be correct, optional roles that are nice-to-have but not
# required, roles that must resolve to None).
CASES = [
    (
        "Standard retail",
        pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "Product": ["A", "B", "A"],
            "Category": ["X", "Y", "X"],
            "Quantity": [1, 2, 1],
            "Price": [100, 200, 100],
            "Total": [100, 400, 100],
            "Region": ["North", "South", "North"],
        }),
        {"date": "Date", "amount": "Total", "quantity": "Quantity", "product": "Product", "category": "Category", "region": "Region"},
        [], [],
    ),
    (
        "Abbreviated Indian retail (Dept/Town)",
        pd.DataFrame({
            "Bill Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "Item Name": ["Cup", "Tray", "Cup"],
            "Dept": ["Kitchenware", "Decor", "Kitchenware"],
            "Qty": [1, 2, 1],
            "Grand Total": [100, 400, 100],
            "Town": ["Pune", "Mumbai", "Pune"],
        }),
        {"date": "Bill Date", "amount": "Grand Total", "quantity": "Qty", "product": "Item Name", "category": "Dept", "region": "Town"},
        [], [],
    ),
    (
        "E-commerce (SKU/Revenue/State)",
        pd.DataFrame({
            "Order Date": ["2024-01-01", "2024-01-02"],
            "SKU": ["SKU1", "SKU2"],
            "Product Category": ["Electronics", "Apparel"],
            "Units Sold": [1, 3],
            "Unit Price": [500, 200],
            "Revenue": [500, 600],
            "Customer State": ["Maharashtra", "Gujarat"],
        }),
        {"date": "Order Date", "amount": "Revenue", "quantity": "Units Sold", "product": "SKU", "category": "Product Category", "region": "Customer State"},
        [], [],
    ),
    (
        "Restaurant (Menu Item/Outlet City)",
        pd.DataFrame({
            "Order Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "Menu Item": ["Pizza", "Pasta", "Pizza"],
            "Item Type": ["Main", "Main", "Main"],
            "Covers": [2, 4, 2],
            "Amount": [500, 700, 500],
            "Outlet City": ["Delhi", "Delhi", "Mumbai"],
        }),
        {"date": "Order Date", "amount": "Amount", "product": "Menu Item", "category": "Item Type", "region": "Outlet City"},
        ["quantity"], [],
    ),
    (
        "Freelancer invoices",
        pd.DataFrame({
            "Invoice Date": ["2024-01-01", "2024-01-02"],
            "Service": ["Design", "Development"],
            "Service Category": ["Creative", "Technical"],
            "Amount": [5000, 8000],
            "Client Location": ["Bangalore", "Chennai"],
        }),
        {"date": "Invoice Date", "amount": "Amount", "product": "Service", "category": "Service Category", "region": "Client Location"},
        [], [],
    ),
    (
        "Minimal (date+amount only)",
        pd.DataFrame({"Date": ["2024-01-01", "2024-01-02"], "Amount": [100, 200]}),
        {"date": "Date", "amount": "Amount"},
        [], ["product", "category", "region", "quantity"],
    ),
    (
        "ALL CAPS headers",
        pd.DataFrame({
            "DATE": ["2024-01-01", "2024-01-02"], "PRODUCT": ["A", "B"],
            "CATEGORY": ["X", "Y"], "AMOUNT": [100, 200], "REGION": ["North", "South"],
        }),
        {"date": "DATE", "amount": "AMOUNT", "product": "PRODUCT", "category": "CATEGORY", "region": "REGION"},
        [], [],
    ),
    (
        "Distractor free-text columns",
        pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "Product": ["Chair", "Table", "Chair", "Lamp"],
            "Amount": [1000, 3000, 1000, 500],
            "Notes": ["urgent delivery requested please", "customer asked for gift wrap", "repeat customer discount applied", "n/a"],
            "Salesperson": ["Raj", "Priya", "Raj", "Amit"],
        }),
        {"date": "Date", "amount": "Amount", "product": "Product"},
        [], [],
    ),
    (
        "Currency-suffixed amount column",
        pd.DataFrame({"Date": ["2024-01-01", "2024-01-02"], "Product": ["A", "B"], "Amount (INR)": [100, 200]}),
        {"date": "Date", "amount": "Amount (INR)", "product": "Product"},
        [], [],
    ),
    (
        "Ambiguous numeric columns (Cost vs Total)",
        pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"], "Product": ["A", "B", "A"],
            "Unit Cost": [50, 80, 50], "Qty": [2, 3, 2], "Total Paid": [100, 240, 100],
        }),
        {"date": "Date", "amount": "Total Paid", "product": "Product", "quantity": "Qty"},
        [], [],
    ),
    (
        "Trailing whitespace headers",
        pd.DataFrame({"Date ": ["2024-01-01", "2024-01-02"], "Product ": ["A", "B"], "Amount ": [100, 200]}),
        {"date": "Date ", "amount": "Amount ", "product": "Product "},
        [], [],
    ),
]


def test_column_detection_accuracy_benchmark():
    total_checks = 0
    correct = 0
    failures = []

    for name, df, expected, optional, expect_none in CASES:
        detected = loader.detect_columns(df).as_dict()
        for role, expected_col in expected.items():
            total_checks += 1
            if detected.get(role) == expected_col:
                correct += 1
            else:
                failures.append(f"[{name}] {role}: expected {expected_col!r}, got {detected.get(role)!r}")
        for role in expect_none:
            total_checks += 1
            if detected.get(role) is None:
                correct += 1
            else:
                failures.append(f"[{name}] {role}: expected None, got {detected.get(role)!r}")

    accuracy = 100 * correct / total_checks
    print(f"\nColumn detection accuracy: {correct}/{total_checks} = {accuracy:.1f}%")
    if failures:
        print("Failures:\n" + "\n".join(f"  - {f}" for f in failures))

    # The product bar: at least 90% correct across these realistic
    # schemas. Currently measured at 100% -- this assertion is a floor
    # that must hold, not a target to just barely scrape past.
    assert accuracy >= 90.0, f"Column detection accuracy {accuracy:.1f}% fell below the 90% floor"
    assert not failures, f"{len(failures)} detection failure(s) found (see printed output above)"
