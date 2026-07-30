"""
Assembles the final branded PDF: cover, KPI summary cards, insights,
then one page per chart. Built with fpdf2 (pure Python, no system
dependency like wkhtmltopdf/Chromium) so the tool runs anywhere,
which matters for a free, run-locally, offline product.

Two fpdf2 pitfalls this avoids (learned the hard way during
development):
  1. multi_cell() leaves the cursor at the page's RIGHT edge by
     default (new_x=XPos.RIGHT) instead of the left margin — every
     multi_cell() call below passes new_x=XPos.LMARGIN, new_y=YPos.NEXT
     explicitly, or the next multi_cell(w=0) computes ~0 width and
     raises FPDFException.
  2. Core Helvetica/Arial fonts only support latin-1, which silently
     mangled any non-English business/product name (accented Latin,
     Cyrillic, Greek, Vietnamese, the rupee sign, etc.) into '?'
     characters. Fixed by embedding DejaVu Sans (bundled under
     insightcard/fonts/, redistribution-permitted — see
     fonts/FONT_LICENSE.txt), which covers a much wider Unicode range.

KNOWN LIMITATION: DejaVu Sans does not include Devanagari, Tamil, or
other Indic scripts (nor CJK/Arabic). Product or business names in
those scripts will render as blank/missing-glyph boxes in the PDF —
this is a font-coverage limit, not a crash, and there's no drop-in
pure-Python fix for complex script shaping today. English/Latin-script
names, and most European/Cyrillic text, render correctly.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from insightcard.config import BrandConfig
from insightcard.metrics import ReportMetrics

WHITE = (255, 255, 255)
GREY = (69, 90, 100)
LIGHT_GREY = (236, 239, 241)
GREEN = (46, 125, 50)
RED = (198, 40, 40)

_FONTS_DIR = Path(__file__).parent / "fonts"

# Cosmetic normalization only — DejaVu Sans renders these Unicode
# punctuation marks fine, but a plain hyphen/quote reads more cleanly
# in a printed business report.
_PUNCTUATION_NORMALIZATION = {
    "\u2014": " - ", "\u2013": " - ", "\u00a0": " ",
}


def _clean(text: str) -> str:
    for src, dst in _PUNCTUATION_NORMALIZATION.items():
        text = text.replace(src, dst)
    return text


class _BrandedPDF(FPDF):
    brand: BrandConfig = BrandConfig()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", "I", str(_FONTS_DIR / "DejaVuSans-Oblique.ttf"))

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(*GREY)
        self.cell(0, 10, _clean(f"{self.brand.footer_text}  |  Page {self.page_no()}"), align="C")


def _line(pdf: FPDF, h: float, text: str, **kwargs) -> None:
    pdf.multi_cell(0, h, _clean(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)


def _kpi_card(pdf: FPDF, x: float, y: float, w: float, h: float, label: str, value: str, color) -> None:
    pdf.set_fill_color(*LIGHT_GREY)
    pdf.rect(x, y, w, h, style="F")
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, 3, style="F")
    pdf.set_xy(x + 4, y + 8)
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*color)
    pdf.cell(w - 8, 8, _clean(value))
    pdf.set_xy(x + 4, y + h - 12)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(w - 8, 6, _clean(label))


def build_report(
    metrics: ReportMetrics,
    chart_paths: list[Path],
    brand: BrandConfig,
    output_path: str | Path,
    data_quality=None,
) -> Path:
    pdf = _BrandedPDF(format="A4")
    pdf.brand = brand
    pdf.set_auto_page_break(auto=True, margin=18)

    # ---------------------------------------------------------- cover
    pdf.add_page()
    pdf.set_fill_color(*brand.accent_color)
    pdf.rect(0, 0, 210, 60, style="F")
    pdf.set_xy(15, 18)
    pdf.set_font("DejaVu", "B", 22)
    pdf.set_text_color(*WHITE)
    _line(pdf, 10, brand.report_title)
    pdf.set_xy(15, 38)
    pdf.set_font("DejaVu", "", 13)
    _line(pdf, 7, brand.business_name)
    if metrics.date_range:
        pdf.set_xy(15, 48)
        pdf.set_font("DejaVu", "", 10)
        _line(pdf, 6, f"Period covered: {metrics.date_range[0]} to {metrics.date_range[1]}")

    # KPI cards
    pdf.set_y(72)
    card_w, card_h, gap = 88, 34, 6
    kpis = [
        ("Total Revenue", f"{brand.currency_symbol}{metrics.total_revenue:,.2f}", brand.accent_color),
        ("Orders", f"{metrics.order_count:,}", brand.accent_color),
    ]
    if metrics.growth_pct is not None:
        color = GREEN if metrics.growth_pct >= 0 else RED
        sign = "+" if metrics.growth_pct >= 0 else ""
        kpis.append(("Growth (last period)", f"{sign}{metrics.growth_pct}%", color))
    kpis.append(("Average Order Value", f"{brand.currency_symbol}{metrics.average_order_value:,.2f}", brand.accent_color))

    x0, y0 = 15, pdf.get_y()
    for i, (label, value, color) in enumerate(kpis):
        row, col = divmod(i, 2)
        x = x0 + col * (card_w + gap)
        y = y0 + row * (card_h + gap)
        _kpi_card(pdf, x, y, card_w, card_h, label, value, color)

    pdf.set_y(y0 + 2 * (card_h + gap) + 8)

    # -------------------------------------------------- data health check
    if data_quality is not None:
        pdf.set_font("DejaVu", "B", 13)
        pdf.set_text_color(*brand.accent_color)
        _line(pdf, 8, "Data Health Check")
        pdf.set_font("DejaVu", "", 10)
        if data_quality.is_clean:
            pdf.set_text_color(GREEN[0], GREEN[1], GREEN[2])
            _line(pdf, 6, f"No data quality issues detected across {data_quality.total_rows:,} rows.")
        else:
            pdf.set_text_color(30, 30, 30)
            for warning in data_quality.warnings:
                _line(pdf, 6, f"-  {warning}")
        pdf.ln(2)

    # ------------------------------------------------------- insights
    pdf.set_font("DejaVu", "B", 13)
    pdf.set_text_color(*brand.accent_color)
    _line(pdf, 8, "Key Insights")
    pdf.set_font("DejaVu", "", 10.5)
    pdf.set_text_color(30, 30, 30)
    for insight in metrics.insights:
        _line(pdf, 6, f"-  {insight}")
    pdf.ln(2)

    if metrics.top_products is not None and len(metrics.top_products):
        pdf.set_font("DejaVu", "B", 12)
        pdf.set_text_color(*brand.accent_color)
        _line(pdf, 7, "Top Products")
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(30, 30, 30)
        for rank, (name, revenue) in enumerate(metrics.top_products.items(), start=1):
            _line(pdf, 5.5, f"  {rank}. {name} - {brand.currency_symbol}{revenue:,.2f}")
        pdf.ln(2)

    if metrics.slow_moving_products is not None and len(metrics.slow_moving_products):
        pdf.set_font("DejaVu", "B", 12)
        pdf.set_text_color(RED[0], RED[1], RED[2])
        _line(pdf, 7, "Slow-Moving Stock (no sale in 30+ days)")
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(30, 30, 30)
        for name, days in metrics.slow_moving_products.head(10).items():
            _line(pdf, 5.5, f"  - {name} - last sold {int(days)} days ago")

    # --------------------------------------------------------- charts
    for chart_path in chart_paths:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 13)
        pdf.set_text_color(*brand.accent_color)
        title = chart_path.stem.replace("chart_", "").replace("_", " ").title()
        _line(pdf, 9, title)
        pdf.image(str(chart_path), x=15, w=180)

    output_path = Path(output_path)
    pdf.output(str(output_path))
    return output_path
