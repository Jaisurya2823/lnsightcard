"""
InsightCard web app -- the same engine as generate_report.py, wrapped
in a browser UI so a non-technical user never has to open a terminal:
upload a spreadsheet, click a button, download the report.

Run locally:
    streamlit run app.py

Deploy free (see README "Deploying the web app" section):
    https://share.streamlit.io -- point it at this repo, this file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from insightcard import charts, docx_report, excel_report, loader
from insightcard import data_quality as data_quality_mod
from insightcard import metrics as metrics_mod
from insightcard import pdf_report, txt_report
from insightcard.config import BrandConfig, ColumnMap

st.set_page_config(page_title="InsightCard", page_icon="📊", layout="centered")

st.title("📊 InsightCard")
st.caption("Turn any messy sales spreadsheet into a branded report — no fixed schema needed.")

with st.sidebar:
    st.header("Report details")
    business_name = st.text_input("Business name", value="Your Business")
    currency = st.text_input("Currency symbol", value="Rs ")
    st.markdown("---")
    st.subheader("Column overrides (optional)")
    st.caption("Leave blank to auto-detect. Only fill in if a preview below looks wrong.")
    date_override = st.text_input("Date column", value="")
    amount_override = st.text_input("Amount/Revenue column", value="")
    product_override = st.text_input("Product column", value="")
    category_override = st.text_input("Category column", value="")
    region_override = st.text_input("Region column", value="")
    quantity_override = st.text_input("Quantity column", value="")

uploaded_file = st.file_uploader("Upload your sales/orders file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = Path(tmp.name)

    try:
        df = loader.load_file(tmp_path)
    except Exception as exc:  # noqa: BLE001 -- surface the error to the user, don't crash the app
        st.error(f"Couldn't read this file: {exc}")
        st.stop()

    detected = loader.detect_columns(df)
    columns = ColumnMap(
        date=date_override or detected.date,
        amount=amount_override or detected.amount,
        quantity=quantity_override or detected.quantity,
        product=product_override or detected.product,
        category=category_override or detected.category,
        region=region_override or detected.region,
    )

    st.subheader("Detected columns")
    st.json(columns.as_dict())

    if columns.amount is None:
        st.error(
            "Couldn't automatically find a revenue/amount column. "
            "InsightCard is built for sales/orders data with a money column in it -- "
            "if this file is a catalog, list, or reference sheet without any revenue "
            "figures (e.g. a list of links or products with no prices), this tool isn't "
            "the right fit for it. If it DOES have a revenue column under an unusual "
            "name, enter it in the 'Amount/Revenue column' box in the sidebar."
        )
        st.stop()

    normalized = loader.normalize(df, columns)
    report_metrics = metrics_mod.compute_metrics(normalized)
    quality_report = data_quality_mod.check_data_quality(normalized)

    st.subheader("Key metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"{currency}{report_metrics.total_revenue:,.2f}")
    col2.metric("Orders", f"{report_metrics.order_count:,}")
    col3.metric("Avg Order Value", f"{currency}{report_metrics.average_order_value:,.2f}")
    if report_metrics.growth_pct is not None:
        col4.metric("Growth (last period)", f"{report_metrics.growth_pct:+.1f}%")

    if not quality_report.is_clean:
        st.subheader("⚠️ Data Health Check")
        for warning in quality_report.warnings:
            st.warning(warning)
    else:
        st.success(f"No data quality issues detected across {quality_report.total_rows:,} rows.")

    st.subheader("Key insights")
    for insight in report_metrics.insights:
        st.markdown(f"- {insight}")

    with tempfile.TemporaryDirectory() as out_dir:
        out_dir = Path(out_dir)
        chart_paths = charts.generate_all_charts(report_metrics, out_dir / "charts")

        st.subheader("Charts")
        for chart_path in chart_paths:
            st.image(str(chart_path), use_container_width=True)

        brand = BrandConfig(
            business_name=business_name, currency_symbol=currency, footer_text="Generated with InsightCard"
        )

        st.subheader("Download your report")
        dl_col1, dl_col2, dl_col3, dl_col4 = st.columns(4)

        pdf_path = pdf_report.build_report(
            report_metrics, chart_paths, brand, out_dir / "report.pdf", data_quality=quality_report
        )
        dl_col1.download_button("📄 PDF", pdf_path.read_bytes(), file_name="report.pdf")

        xlsx_path = excel_report.build_workbook(
            report_metrics, brand, out_dir / "report.xlsx", data_quality=quality_report
        )
        dl_col2.download_button("📊 Excel", xlsx_path.read_bytes(), file_name="report.xlsx")

        docx_path = docx_report.build_docx(
            report_metrics, chart_paths, brand, out_dir / "report.docx", data_quality=quality_report
        )
        dl_col3.download_button("📝 Word", docx_path.read_bytes(), file_name="report.docx")

        txt_path = txt_report.build_txt(
            report_metrics, brand, out_dir / "report.txt", data_quality=quality_report
        )
        dl_col4.download_button("🧾 Text", txt_path.read_bytes(), file_name="report.txt")

    tmp_path.unlink(missing_ok=True)
else:
    st.info("Upload a .csv or .xlsx file to get started.")
