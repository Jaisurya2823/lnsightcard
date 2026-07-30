# InsightCard

![InsightCard banner](assets/banner.png)

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Offline](https://img.shields.io/badge/AI%20API%20cost-%240-brightgreen)

Drop in a messy sales/orders spreadsheet, get back a full report package —
branded PDF, editable Excel workbook, Word document, plain text summary,
and the individual chart images — no chat interface, no subscription, no
internet connection required after install.

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

**Where this is honestly positioned**: this is a solid, tested reporting
tool that fills a real gap (see "Is this actually better?" below) — it
is not a replacement for a human analyst or a claim to out-analyze
dedicated BI platforms on complex, multi-year, multi-source data.

## What it does

1. Reads your `.csv` or `.xlsx` file.
2. Automatically detects which column is the date, the amount/revenue,
   the product, the category, the region, etc. — by column name
   keywords first, then by data shape (e.g. the numeric column with
   the largest total is probably revenue).
3. Runs a **Data Health Check** — flags duplicate rows, blank
   dates/amounts, negative revenue (often a miscoded refund), zero-
   amount rows, and unusually large orders (a classic typo — an extra
   zero) — the everyday mistakes that quietly distort totals in a
   hand-maintained spreadsheet.
4. Computes total revenue, order count, average order value,
   period-over-period growth, top products/categories/regions, best/
   worst day of the week, slow-moving stock (products with no sale in
   30+ days), and a handful of plain-English insights — all
   rule-based, not an LLM call, so there's no ongoing API cost per
   report and it never invents a finding the data doesn't support.
5. Generates whichever of these you ask for, all in one output folder:
   - **PDF** — branded, print-ready report
   - **Excel (.xlsx)** — multi-sheet workbook with live, editable
     native charts (not embedded images) so you can filter/sort/pivot
     further yourself
   - **Word (.docx)** — same content, editable before sharing
   - **Plain text (.txt)** — for pasting into WhatsApp/email
   - **Chart images (.png)** — always generated, usable on their own

## Known limitation: non-Latin scripts

Product/business names in English or most European languages (accented
Latin, Cyrillic, Greek) render correctly. **Devanagari, Tamil, and other
Indic scripts (as well as CJK and Arabic) are not currently supported**
in the PDF/chart output — they'll show as blank boxes. This is a
font-coverage limitation (proper rendering needs a complex-script-
shaping font and engine), not a crash, and it's an open item rather
than something silently broken. If this matters for your use case,
open an issue.

## Project structure

```
insightcard/
├── generate_report.py              # CLI entrypoint
├── insightcard/
│   ├── config.py                    # BrandConfig / ColumnMap
│   ├── loader.py                     # file loading + auto column detection
│   ├── metrics.py                     # stats + rule-based insight sentences
│   ├── data_quality.py                # duplicate/missing/outlier detection
│   ├── charts.py                       # matplotlib chart generation
│   ├── pdf_report.py                    # fpdf2 branded PDF assembly
│   ├── excel_report.py                   # openpyxl workbook + native charts
│   ├── docx_report.py                     # python-docx Word document
│   ├── txt_report.py                       # plain text summary
│   └── fonts/                                # embedded DejaVu Sans (see FONT_LICENSE.txt)
├── tests/
│   ├── test_loader_and_metrics.py
│   ├── test_data_quality_and_daily_ops.py
│   └── test_exporters.py
├── requirements.txt
├── LICENSE
└── assets/banner.png
```

Note: there is no committed `output/` folder — report files are
generated fresh, in a folder next to whatever input file you run the
tool on (see Usage below), and are gitignored so generated output
never gets committed alongside the source code.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Point it at your own sales/orders file
python generate_report.py my_orders.xlsx --business-name "Sharma Store"

# Generate every format at once
python generate_report.py my_orders.xlsx --business-name "Sharma Store" --formats all

# Just PDF + Excel
python generate_report.py my_orders.xlsx --business-name "Sharma Store" --formats pdf,excel

# Choose where the output folder goes
python generate_report.py my_orders.xlsx --business-name "Sharma Store" --output-dir ./my_report

# See what columns were auto-detected without generating anything
python generate_report.py my_orders.xlsx --show-columns

# Force a specific column if auto-detection picks the wrong one
python generate_report.py my_orders.csv --amount-col "Grand Total" --date-col "Bill Date"
```

**Where your files end up**: everything lands in
`<input file name>_report/` next to your input file (or wherever
`--output-dir` points) — e.g. `my_orders_report/report.pdf`,
`report.xlsx`, `report.docx`, `report.txt`, and a `charts/` folder with
each chart as its own PNG. Open that folder directly, or copy/zip it
to share — it's a normal folder on your computer, nothing stays inside
this tool.

Flags: `--business-name`, `--report-title`, `--output-dir`, `--formats`
(comma-separated: `pdf`, `excel`, `docx`, `txt`, or `all`; default
`pdf`), `--currency` (defaults to `Rs `), `--footer-text`, and one
override flag per column role (`--date-col`, `--amount-col`,
`--quantity-col`, `--product-col`, `--category-col`, `--region-col`).

## Tests

```bash
python -m pytest tests/
```

28 tests, covering column detection, metrics, data quality checks, all
four export formats, and a **column-detection accuracy benchmark**
across 12 realistic business spreadsheet schemas (standard retail,
abbreviated Indian retail, e-commerce, restaurant, freelancer
invoices, and several adversarial cases) — currently measuring **100%**
against a required floor of 90%, enforced as a test assertion so a
future change can't silently regress it. Includes regression tests for
several real bugs found via this kind of stress testing (see below).

## Bugs found and fixed via stress testing

In the interest of not overselling this, here's what deliberate,
realistic stress testing actually turned up and how it was fixed —
rather than just asserting the tool is reliable:

- **Unicode/accented text was silently mangled** in the PDF (forced
  latin-1 encoding turned `Café`, `€` into `?`). Fixed by embedding
  DejaVu Sans.
- **Category and region got detected backwards** on abbreviated
  headers (`Dept`/`Town`) because neither matched the keyword lists,
  so a cardinality-based fallback grabbed the wrong one. Fixed by
  adding common abbreviations/synonyms to the keyword lists.
- **Product and category got swapped** (`SKU` vs `Product Category`)
  because the generic keyword `product` matched inside the compound
  column name `Product Category` before the more specific `sku`
  keyword was ever checked against the real SKU column. Fixed by
  making an exact column-name match always beat a partial/substring
  match, regardless of keyword priority order.
- **Growth percentage could explode into a nonsensical figure**
  (e.g. "dropped 2476.7%") when the previous period's net revenue was
  zero or negative (a month dominated by a refund). Fixed by not
  reporting a growth percentage at all when the baseline period isn't
  positive, rather than showing a misleading number.
- **A "top 3 products" share could exceed 100%** when refunds are
  coded as their own negative-amount line item (common in real
  exports) rather than netted against the original sale, making net
  total revenue smaller than the sum of individual products' positive
  totals. Fixed by using gross positive revenue as the denominator for
  share-of-revenue percentages, and by refusing to print a share
  figure at all if it would still come out above 100%.

All five are covered by permanent regression tests, and a 12-schema
column-detection accuracy benchmark (100% currently, enforced floor at
90%) runs as part of the test suite so future changes can't silently
undo any of this.

## Is this actually better than existing solutions?

Being direct rather than promotional: it depends what you're comparing
it to.

- **Vs. Excel/Google Sheets alone**: yes, clearly — this automates
  column detection, computes the insights a business owner would
  otherwise have to work out manually, and catches data-entry mistakes
  (duplicates, typos, refunds) that go unnoticed in a raw spreadsheet.
- **Vs. Power BI / Tableau**: not for power users doing complex,
  ongoing, multi-source analysis — those tools are more capable and
  that's not this tool's goal. This wins on setup time (seconds, not
  hours of modeling) and cost (free vs. licensing/infra) for a business
  owner who just wants a report, not a BI practice.
- **Vs. Julius AI / ChatGPT Advanced Data Analysis / similar AI tools**:
  this trades away open-ended conversational analysis for something
  those tools don't offer — zero ongoing API cost, works fully offline,
  and doesn't send your sales data to a third-party API at all. Worse
  for exploratory "ask it anything" analysis; better for a fixed,
  predictable, repeatable report on sensitive business data.
- **The honest gap**: this hasn't been used on messy data from outside
  the examples built during development — real-world spreadsheets will
  surface edge cases the test suite doesn't cover yet. Treat it as a
  solid first release, not a finished, battle-tested product.

## Design choices

- **Rebranding**: everything customer-facing lives in `BrandConfig`
  (business name, report title, accent color, footer, currency
  symbol) — no code changes needed to reskin a report for a different
  business.
- **No LLM calls**: insights are rule-based templates over computed
  numbers, not an API call — the tool works fully offline and never
  invents a finding that isn't backed by the data.
- **Contributions welcome**: new metrics, chart types, export formats,
  or column-role detectors are all self-contained additions — see
  "Extending it" below.

## Extending it

- New metric: add a function to `metrics.py`, then reference it from
  `_build_insights()` or add it to the KPI cards in `pdf_report.py`.
- New chart: add a `plot_*` function to `charts.py` following the same
  "return None if the data isn't there" pattern, then add it to
  `generate_all_charts()`.
- New export format: follow the pattern in `txt_report.py` (simplest)
  or `excel_report.py`/`docx_report.py` — each takes `ReportMetrics`
  plus an optional `DataQualityReport` and writes one file.
- Custom logo instead of a plain color banner: swap the `pdf.rect(...)`
  banner in `pdf_report.py`'s cover section for `pdf.image(logo_path, ...)`.

## Deployment — using this in the real world

The CLI (`generate_report.py`) is the core engine and needs no
deployment — anyone with Python can clone the repo and run it. But a
non-technical shop owner won't open a terminal, so there's also a
browser-based version: `app.py`, a Streamlit web app that wraps the
same tested engine (loader → metrics → data quality → charts →
PDF/Excel/Word/text export) behind an upload button and download
buttons. No separate backend/frontend to build — it's the existing
package, verified to produce identical output through this UI.

**Run it locally first:**
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opens at `http://localhost:8501` — upload a file, see the metrics and
charts inline, download whichever formats you want.

**Deploy it for free, get a public URL, in about 5 minutes:**
1. Push this repo to GitHub (see commands below).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub.
3. Click "New app" → pick this repo → set the main file to `app.py` →
   Deploy.
4. You get a URL like `https://insightcard.streamlit.app` — share that
   directly with anyone; they use it in a browser, no install required.

This is the free tier of Streamlit Community Cloud — fine for personal
use or sharing with a small number of people. If usage grows, the same
`app.py` also runs on Render, Railway, or Fly.io's free/hobby tiers
with minimal changes (just a `Procfile`/start command pointing at
`streamlit run app.py --server.port $PORT`).

**Other deployment options, if the audience needs them:**
- **Desktop `.exe` (zero install, fully offline)**: `pip install pyinstaller`
  then `pyinstaller --onefile generate_report.py` — produces a single
  Windows executable for someone who won't install Python at all. Best
  for the CLI, not the Streamlit version.
- **PyPI package**: `pip install insightcard` instead of cloning the
  repo — worth doing once the API is stable; not done yet.

## GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/Jaisurya2823/lnsightcard.git
git push -u origin main
```

## Author

**Jai Surya** ([@Jaisurya2823](https://github.com/Jaisurya2823))

## License

MIT — see [LICENSE](LICENSE). Embedded fonts under `insightcard/fonts/`
are separately licensed — see `insightcard/fonts/FONT_LICENSE.txt`.
