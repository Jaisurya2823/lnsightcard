"""
Loads a CSV/Excel file and figures out which column plays which role
(date, amount, quantity, product, category, region) WITHOUT requiring
the user to rename anything first — this is the whole point of the
product: a small business's export from Excel, Meesho, or a billing
tool almost never matches a fixed schema, so detection has to be
heuristic, not exact-name matching.

Detection strategy per role:
  - date:      try parsing each object/datetime-like column as dates;
               pick the one with the highest successful-parse rate
  - amount:    prefer a numeric column whose name matches known
               keywords (revenue/amount/total/sales/price/value);
               otherwise fall back to the numeric column with the
               largest sum (revenue columns are usually the biggest
               numbers in a sales file)
  - quantity:  numeric column matching qty/quantity/units/count
  - product:   string column matching product/item/sku/name;
               otherwise the string column with the most unique values
               (products vary a lot; categories don't)
  - category:  string column matching category/type/segment/class;
               otherwise a string column with low cardinality (<=30
               unique values) that isn't already picked as product
  - region:    string column matching region/state/city/location

Every guess can be overridden by the caller (the CLI exposes
--date-col etc.) — detection is a convenience default, not a lock-in.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from insightcard.config import ColumnMap

_DATE_KEYWORDS = ["date", "day", "timestamp", "created", "order date"]
_AMOUNT_KEYWORDS = ["total", "revenue", "amount", "grand total", "sales", "value", "price", "cost"]
_QUANTITY_KEYWORDS = ["qty", "quantity", "units", "count", "no. of", "copies", "nos", "pcs", "pieces"]
_PRODUCT_KEYWORDS = ["product", "item", "sku", "description", "service", "dish", "medicine", "book title"]
_CATEGORY_KEYWORDS = ["category", "segment", "department", "dept", "type", "class", "genre"]
_REGION_KEYWORDS = ["region", "state", "city", "town", "district", "location", "area", "branch", "zone", "outlet"]

# Exact (normalized, alphanumeric-only) column names that are almost
# always a row index / serial number, never a real quantity or amount.
# Checked as an EXACT match against the normalized name -- not a
# substring -- so this never fires on something like 'Paid Amount'
# (which contains the letters 'id' but isn't equal to the word 'id').
_ID_COLUMN_NAMES = {
    "sno", "srno", "slno", "serialno", "serialnumber", "sourceno",
    "id", "index", "rowno", "row", "no", "num", "number",
}

# Columns that look like a person's identity, not a business dimension.
# A "Student Name" or "Client Name" column has high text cardinality --
# the same shape a real product/category column has -- so without this
# denylist it can get mistaken for one (worse, it would put customer
# names in a "top categories" or "top regions" list in the report).
# These columns are excluded from product/category/region detection
# entirely rather than guessed at.
_IDENTIFIER_DENYLIST = [
    "customer", "client", "student", "patient", "employee", "staff",
    "buyer", "vendor", "supplier", "contact", "salesperson", "cashier",
]

_MAX_CATEGORY_CARDINALITY = 30


def load_file(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file type '{path.suffix}'. Use .csv, .xlsx, or .xls.")


def _name_matches(col_name: str, keywords: list[str]) -> bool:
    lowered = col_name.strip().lower()
    return any(kw in lowered for kw in keywords)


def _is_text_column(series: pd.Series) -> bool:
    """True for legacy object-dtype string columns AND pandas 3.0's
    native StringDtype ('str') — pandas 3.0 defaults text columns to
    the latter, so checking `dtype == object` alone (which worked
    fine through pandas 2.x) silently misses every text column on a
    pandas 3.0 install."""
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)


def _best_date_column(df: pd.DataFrame) -> str | None:
    candidates = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            candidates.append((col, 1.0, _name_matches(col, _DATE_KEYWORDS)))
            continue
        if _is_text_column(df[col]):
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            success_rate = parsed.notna().mean()
            if success_rate > 0.6:
                candidates.append((col, success_rate, _name_matches(col, _DATE_KEYWORDS)))
    if not candidates:
        return None
    # prefer a name-keyword match, then highest parse success rate
    candidates.sort(key=lambda c: (c[2], c[1]), reverse=True)
    return candidates[0][0]


def _first_by_keyword_priority(columns: list[str], keywords: list[str]) -> str | None:
    """Returns the best column for a role's keyword list, in two passes:

    Pass 1 -- EXACT match (column name, stripped/lowercased, equals the
    keyword exactly) wins first, checked across ALL keywords before any
    substring match is considered. This matters because a compound
    column name can innocently contain another role's keyword as a
    substring -- e.g. 'Product Category' contains 'product', which
    would otherwise steal that column away from the product role's
    more specific 'sku' keyword matching an actual 'SKU' column.

    Pass 2 -- substring match, in keyword priority order (position in
    `keywords`), same as before -- used only if no exact match exists
    for any keyword.
    """
    for kw in keywords:
        for col in columns:
            if col.strip().lower() == kw:
                return col
    for kw in keywords:
        for col in columns:
            if kw in col.strip().lower():
                return col
    return None


def _is_id_like_column(series: pd.Series, col_name: str) -> bool:
    """True if a numeric column looks like a row index / serial number
    rather than a real quantity — this is what let 'S.No' (1, 2, 3...)
    get mistaken for revenue on a course-catalog file that had no real
    amount column at all (see the accuracy benchmark / bug history for
    the case that caught this).

    Checked two ways, since either alone can miss real cases:
      - by name: normalized column name is exactly a known ID pattern
        ('s.no' -> 'sno', 'sr no' -> 'srno', 'id', 'index', etc.) --
        an EXACT match on the alphanumeric-only name, not a substring,
        so this never false-positives on something like 'Paid Amount'
        (which contains 'id' as a substring but isn't equal to it)
      - by shape: the values are a perfect 1-step arithmetic sequence
        (1,2,3,4... or 0,1,2,3...) -- the unmistakable signature of a
        row counter, regardless of what the column happens to be named
    """
    normalized = "".join(ch for ch in col_name.lower() if ch.isalnum())
    if normalized in _ID_COLUMN_NAMES:
        return True

    clean = series.dropna()
    if len(clean) < 3:
        return False
    if not pd.api.types.is_integer_dtype(clean) and not (clean == clean.round()).all():
        return False
    sorted_vals = clean.sort_values().reset_index(drop=True)
    diffs = sorted_vals.diff().dropna()
    return bool((diffs == 1).all())


def _best_numeric_column(df: pd.DataFrame, keywords: list[str], exclude: set[str]) -> str | None:
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in exclude]
    if not numeric_cols:
        return None
    return _first_by_keyword_priority(numeric_cols, keywords)


def _largest_sum_column(df: pd.DataFrame, exclude: set[str]) -> str | None:
    """Fallback when no amount keyword matches anything: guess the
    numeric column with the largest sum (a real revenue column is
    usually the biggest number in a sales file). ID-like columns are
    excluded from this guess entirely -- see _is_id_like_column -- so
    a serial number is never picked over having no amount column at
    all. Returning None here is the CORRECT outcome for a file that
    genuinely has no revenue data (the CLI/app already handle that by
    telling the user to specify --amount-col explicitly)."""
    numeric_cols = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and c not in exclude and not _is_id_like_column(df[c], c)
    ]
    if not numeric_cols:
        return None
    sums = {c: df[c].sum() for c in numeric_cols}
    return max(sums, key=sums.get)


def _is_identifier_column(col_name: str) -> bool:
    lowered = col_name.strip().lower()
    return any(kw in lowered for kw in _IDENTIFIER_DENYLIST)


def _keyword_match_string_column(df: pd.DataFrame, keywords: list[str], exclude: set[str]) -> str | None:
    """Keyword matching intentionally does NOT apply the identifier
    denylist: a column like 'Customer State' or 'Client Location'
    contains a real, specific region keyword ('state'/'location') and
    should win on that basis even though it also contains a generic
    word like 'customer'/'client'. The denylist only protects the
    fallback phase below, where there's no keyword to justify the
    guess in the first place."""
    string_cols = [c for c in df.columns if _is_text_column(df[c]) and c not in exclude]
    if not string_cols:
        return None
    return _first_by_keyword_priority(string_cols, keywords)


def _fallback_string_column(
    df: pd.DataFrame, exclude: set[str], max_cardinality: int | None = None
) -> str | None:
    """Cardinality-based guessing, with no keyword to justify the pick --
    this is exactly the situation where a bare 'Client Name'/'Student
    Name' column could otherwise get mistaken for a product/category/
    region, so the identifier denylist applies here."""
    string_cols = [
        c for c in df.columns
        if _is_text_column(df[c]) and c not in exclude and not _is_identifier_column(c)
    ]
    if not string_cols:
        return None
    cardinalities = {c: df[c].nunique() for c in string_cols}
    if max_cardinality is not None:
        eligible = {c: n for c, n in cardinalities.items() if n <= max_cardinality}
        if eligible:
            return max(eligible, key=eligible.get)
        return None
    return max(cardinalities, key=cardinalities.get)


def detect_columns(df: pd.DataFrame) -> ColumnMap:
    used: set[str] = set()

    date_col = _best_date_column(df)
    if date_col:
        used.add(date_col)

    quantity_col = _best_numeric_column(df, _QUANTITY_KEYWORDS, exclude=used)
    if quantity_col:
        used.add(quantity_col)

    amount_col = _best_numeric_column(df, _AMOUNT_KEYWORDS, exclude=used)
    if not amount_col:
        amount_col = _largest_sum_column(df, exclude=used)
    if amount_col:
        used.add(amount_col)

    # Phase 1: keyword matching only, across ALL three string roles,
    # before any role is allowed to fall back to a cardinality guess.
    # Doing this in one combined pass (rather than product-then-
    # category-then-region, each with its own fallback) is what fixes
    # cases like 'Center Location' -- without it, an earlier role's
    # fallback can steal a column that a later role's keyword would
    # have correctly claimed.
    product_col = _keyword_match_string_column(df, _PRODUCT_KEYWORDS, exclude=used)
    if product_col:
        used.add(product_col)
    category_col = _keyword_match_string_column(df, _CATEGORY_KEYWORDS, exclude=used)
    if category_col:
        used.add(category_col)
    region_col = _keyword_match_string_column(df, _REGION_KEYWORDS, exclude=used)
    if region_col:
        used.add(region_col)

    # Phase 2: cardinality-based fallback, only for roles still unfilled.
    if product_col is None:
        product_col = _fallback_string_column(df, exclude=used)
        if product_col:
            used.add(product_col)
    if category_col is None:
        category_col = _fallback_string_column(df, exclude=used, max_cardinality=_MAX_CATEGORY_CARDINALITY)
        if category_col:
            used.add(category_col)
    if region_col is None:
        region_col = _fallback_string_column(df, exclude=used, max_cardinality=_MAX_CATEGORY_CARDINALITY)
        if region_col:
            used.add(region_col)

    return ColumnMap(
        date=date_col, amount=amount_col, quantity=quantity_col,
        product=product_col, category=category_col, region=region_col,
    )


def normalize(df: pd.DataFrame, columns: ColumnMap) -> pd.DataFrame:
    """Returns a copy with standardized column names (date/amount/...)
    so every downstream function (metrics.py, charts.py) only ever has
    to know the logical name, never the user's original header text."""
    rename_map = {v: k for k, v in columns.as_dict().items() if v is not None}
    normalized = df.rename(columns=rename_map).copy()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce", format="mixed")
    if "amount" in normalized.columns:
        normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce")
    return normalized
