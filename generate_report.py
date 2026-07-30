"""
InsightCard -- drop in a sales spreadsheet, get back a full report
package: branded PDF, editable Excel workbook, Word document, plain
text summary, and the individual chart images -- all in one output
folder.

Usage:
    python generate_report.py data.xlsx --business-name "Sharma Store"
    python generate_report.py data.csv --business-name "Sharma Store" --formats pdf,excel
    python generate_report.py data.csv --amount-col "Total (Rs)" --date-col "Order Date"

Column auto-detection handles most real-world exports on its own --
only pass --*-col flags if a report looks wrong and you want to force
a specific column.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from insightcard import charts, docx_report, excel_report, loader
from insightcard import data_quality as data_quality_mod
from insightcard import metrics as metrics_mod
from insightcard import pdf_report, txt_report
from insightcard.config import BrandConfig, ColumnMap

_ALL_FORMATS = ["pdf", "excel", "docx", "txt"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a branded business insights report from a spreadsheet.")
    parser.add_argument("input_file", help="Path to a .csv or .xlsx sales/orders file")
    parser.add_argument("--business-name", default="Your Business", help="Shown on the report cover")
    parser.add_argument("--report-title", default="Business Insights Report")
    parser.add_argument(
        "--output-dir", default=None,
        help="Folder to write all report files into (default: <input file name>_report/ next to the input file)",
    )
    parser.add_argument(
        "--formats", default="pdf",
        help=f"Comma-separated list of formats to generate: {', '.join(_ALL_FORMATS)}, or 'all'. Default: pdf",
    )
    parser.add_argument("--currency", default="Rs ", help="Currency symbol/prefix, e.g. 'Rs ', '$', 'Rs. '")
    parser.add_argument("--footer-text", default="Generated with InsightCard")
    parser.add_argument("--date-col", default=None, help="Force a specific column as the date")
    parser.add_argument("--amount-col", default=None, help="Force a specific column as revenue/amount")
    parser.add_argument("--quantity-col", default=None)
    parser.add_argument("--product-col", default=None)
    parser.add_argument("--category-col", default=None)
    parser.add_argument("--region-col", default=None)
    parser.add_argument("--show-columns", action="store_true", help="Print detected column mapping and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    requested = {f.strip().lower() for f in args.formats.split(",")}
    if "all" in requested:
        requested = set(_ALL_FORMATS)
    unknown = requested - set(_ALL_FORMATS)
    if unknown:
        print(f"Unknown format(s): {', '.join(sorted(unknown))}. Valid: {', '.join(_ALL_FORMATS)}, all", file=sys.stderr)
        sys.exit(1)

    df = loader.load_file(input_path)
    detected = loader.detect_columns(df)

    # CLI overrides win over auto-detection, field by field.
    columns = ColumnMap(
        date=args.date_col or detected.date,
        amount=args.amount_col or detected.amount,
        quantity=args.quantity_col or detected.quantity,
        product=args.product_col or detected.product,
        category=args.category_col or detected.category,
        region=args.region_col or detected.region,
    )

    print("Detected columns:")
    for role, col in columns.as_dict().items():
        print(f"  {role:<10} -> {col!r}")

    if args.show_columns:
        return

    if columns.amount is None:
        print(
            "\nCould not find a revenue/amount column automatically. InsightCard is "
            "built for sales/orders data with a money column -- if this file is a "
            "catalog, list, or reference sheet with no revenue figures, this tool "
            "isn't the right fit for it. If it DOES have a revenue column under an "
            "unusual name, re-run with --amount-col \"<your column name>\".",
            file=sys.stderr,
        )
        sys.exit(1)

    normalized = loader.normalize(df, columns)
    report_metrics = metrics_mod.compute_metrics(normalized)
    quality_report = data_quality_mod.check_data_quality(normalized)

    output_dir = Path(args.output_dir) if args.output_dir else input_path.with_name(f"{input_path.stem}_report")
    charts_dir = output_dir / "charts"
    chart_paths = charts.generate_all_charts(report_metrics, charts_dir)

    brand = BrandConfig(
        business_name=args.business_name,
        report_title=args.report_title,
        currency_symbol=args.currency,
        footer_text=args.footer_text,
    )

    generated: list[Path] = list(chart_paths)  # chart PNGs are always generated -- they're the "images" format

    if "pdf" in requested:
        path = pdf_report.build_report(
            report_metrics, chart_paths, brand, output_dir / "report.pdf", data_quality=quality_report
        )
        generated.append(path)

    if "excel" in requested:
        path = excel_report.build_workbook(
            report_metrics, brand, output_dir / "report.xlsx", data_quality=quality_report
        )
        generated.append(path)

    if "docx" in requested:
        path = docx_report.build_docx(
            report_metrics, chart_paths, brand, output_dir / "report.docx", data_quality=quality_report
        )
        generated.append(path)

    if "txt" in requested:
        path = txt_report.build_txt(
            report_metrics, brand, output_dir / "report.txt", data_quality=quality_report
        )
        generated.append(path)

    print(f"\nAll files saved to: {output_dir}/")
    for path in generated:
        print(f"  - {path.relative_to(output_dir)}")

    if not quality_report.is_clean:
        print("\nData Health Check:")
        for warning in quality_report.warnings:
            print(f"  ! {warning}")
    print("\nKey Insights:")
    for insight in report_metrics.insights:
        print(f"  - {insight}")


if __name__ == "__main__":
    main()
