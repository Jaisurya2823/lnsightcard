# InsightCard

![InsightCard banner](assets/banner.png)

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Offline](https://img.shields.io/badge/AI%20API%20cost-%240-brightgreen)

Drop in a messy sales/orders spreadsheet, get back a branded, print-ready
PDF report — no chat interface, no monthly subscription, no internet
connection required after install.

Built for small sellers, coaching centres, and shop owners whose "data"
is a real Excel/CSV export with inconsistent column names — not a
clean, pre-formatted dataset. Column detection is automatic; nothing
needs to be renamed first.

## Why this exists

Most AI data-analysis tools in 2026 (Julius AI, ChatGPT's Advanced Data
Analysis, Anomaly AI, Statspresso, etc.) are built as SaaS products
aimed at teams with a live data warehouse, priced and packaged for
that audience. That's the wrong shape for a solo shop owner, a
Meesho/Instagram seller, or a small coaching centre tracking orders in
Excel — they need a report, not a subscription or a chat window.
InsightCard is a free, open-source, run-locally tool built for
exactly that.

## What it does

1. Reads your `.csv` or `.xlsx` file.
2. Automatically detects which column is the date, the amount/revenue,
   the product, the category, the region, etc. — by column name
   keywords first, then by data shape (e.g. the numeric column with
   the largest total is probably revenue).
3. Computes total revenue, order count, average order value,
   period-over-period growth, top products/categories/regions, and a
   handful of plain-English insights — all rule-based, not an LLM
   call, so there's no ongoing API cost per report.
4. Renders 3-4 charts and assembles everything into a branded PDF with
   your business name on the cover.

## Project structure

```
insightcard/
├── generate_report.py          # CLI entrypoint
├── insightcard/
│   ├── config.py                # BrandConfig / ColumnMap
│   ├── loader.py                 # file loading + auto column detection
│   ├── metrics.py                 # stats + rule-based insight sentences
│   ├── charts.py                   # matplotlib chart generation
│   └── pdf_report.py                # fpdf2 branded PDF assembly
├── sample_data/
│   └── sample_meesho_orders.xlsx  # example messy export to try it on
├── tests/
│   └── test_loader_and_metrics.py
├── requirements.txt
└── output/                       # generated PDFs land here
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Try it on the included sample data first
python generate_report.py sample_data/sample_meesho_orders.xlsx --business-name "Priya Fashion Store"

# On your own file
python generate_report.py my_orders.xlsx --business-name "Sharma Store" --output report.pdf

# See what columns were auto-detected without generating a report
python generate_report.py my_orders.xlsx --show-columns

# Force a specific column if auto-detection picks the wrong one
python generate_report.py my_orders.csv --amount-col "Grand Total" --date-col "Bill Date"
```

Flags: `--business-name`, `--report-title`, `--output`, `--currency`
(defaults to `Rs `), `--footer-text`, and one override flag per column
role (`--date-col`, `--amount-col`, `--quantity-col`, `--product-col`,
`--category-col`, `--region-col`).

## Tests

```bash
python -m pytest tests/
```

## Design choices

- **Rebranding**: everything customer-facing lives in `BrandConfig`
  (business name, report title, accent color, footer, currency
  symbol) — no code changes needed to reskin a report for a different
  business.
- **No LLM calls**: insights are rule-based templates over computed
  numbers, not an API call — the tool works fully offline and never
  invents a finding that isn't backed by the data.
- **Contributions welcome**: new metrics, chart types, or column-role
  detectors are all self-contained additions — see "Extending it"
  below.

## Extending it

- New metric: add a function to `metrics.py`, then reference it from
  `_build_insights()` or add it to the KPI cards in `pdf_report.py`.
- New chart: add a `plot_*` function to `charts.py` following the same
  "return None if the data isn't there" pattern, then add it to
  `generate_all_charts()`.
- Custom logo instead of a plain color banner: swap the `pdf.rect(...)`
  banner in `pdf_report.py`'s cover section for `pdf.image(logo_path, ...)`.

## Author

**Jai Surya** ([@Jaisurya2823](https://github.com/Jaisurya2823))

## License

MIT — see [LICENSE](LICENSE).